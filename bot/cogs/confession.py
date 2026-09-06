from datetime import timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_session
from bot.database.models import Server
from bot.database.repository import ConfessionRepository, RestrictionRepository, ServerRepository
from bot.services.logging_service import send_moderation_log
from bot.services.security_service import evaluate_submission, record_and_check_burst
from bot.utils.embeds import moderation_confession_embed, public_confession_embed
from bot.utils.helpers import contains_sensitive_keywords, extract_confession_id, extract_confession_id_from_footer
from bot.utils.permissions import can_moderate


REVIEW_TITLE_PREFIX = "Confession #"


def _confession_id_from_message(message: discord.Message | None, prefix: str) -> int | None:
    if not message or not message.embeds:
        return None
    return extract_confession_id(message.embeds[0].title, prefix)


def _confession_id_from_public_message(message: discord.Message | None) -> int | None:
    if not message or not message.embeds:
        return None
    footer = message.embeds[0].footer
    return extract_confession_id_from_footer(footer.text if footer else None)


async def post_public_confession(
    guild: discord.Guild,
    servers: ServerRepository,
    server: Server,
    confession_id: int,
    content: str,
    parent_id: int | None = None,
    reference_message_id: int | None = None,
    reply_number: int | None = None,
) -> discord.Message:
    channel = guild.get_channel(server.confession_channel_id) if server.confession_channel_id else None
    if not isinstance(channel, discord.TextChannel):
        raise ValueError("The configured confession channel is missing or is not a text channel.")

    reference = None
    if reference_message_id:
        reference = discord.MessageReference(
            message_id=reference_message_id,
            channel_id=channel.id,
            fail_if_not_exists=False,
        )

    message = await channel.send(
        embed=public_confession_embed(confession_id, content, parent_id=parent_id, reply_number=reply_number, theme=server.theme),
        view=PublicConfessionView(),
        reference=reference,
        mention_author=False,
    )

    previous_message_id = server.last_confession_message_id
    if previous_message_id and previous_message_id != message.id:
        try:
            await channel.get_partial_message(previous_message_id).edit(view=ReplyOnlyView())
        except discord.HTTPException:
            pass

    await servers.set_last_confession_message(server.id, message.id)

    return message


class ConfessionModal(discord.ui.Modal, title="Submit a Confession"):
    message = discord.ui.TextInput(
        label="Your confession",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await submit_confession(interaction, str(self.message))


class ReplyModal(discord.ui.Modal):
    message = discord.ui.TextInput(
        label="Your reply",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True,
    )

    def __init__(self, parent_id: int):
        super().__init__(title=f"Reply to Confession #{parent_id}"[:45])
        self.parent_id = parent_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await submit_confession(interaction, str(self.message), parent_id=self.parent_id)


class RejectModal(discord.ui.Modal, title="Reject confession"):
    reason = discord.ui.TextInput(label="Reason (optional)", required=False, max_length=500, style=discord.TextStyle.paragraph)

    def __init__(self, confession_id: int):
        super().__init__()
        self.confession_id = confession_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await review_confession(interaction, self.confession_id, "rejected", str(self.reason) or None)


class ReplyOnlyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💬 Reply", style=discord.ButtonStyle.secondary, custom_id="confession:reply")
    async def reply(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        confession_id = _confession_id_from_public_message(interaction.message)
        if confession_id is None:
            await interaction.response.send_message("❌ Could not determine which confession this is.", ephemeral=True)
            return
        await interaction.response.send_modal(ReplyModal(confession_id))


class PublicConfessionView(ReplyOnlyView):
    def __init__(self):
        super().__init__()
        submit_button = discord.ui.Button(
            label="📝 Submit a Confession",
            style=discord.ButtonStyle.primary,
            custom_id="confession:submit",
        )
        submit_button.callback = self.submit
        self.add_item(submit_button)

    async def submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(ConfessionModal())


class ModerationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="confession:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        confession_id = _confession_id_from_message(interaction.message, REVIEW_TITLE_PREFIX)
        if confession_id is None:
            await interaction.response.send_message("❌ This review message is invalid.", ephemeral=True)
            return
        await review_confession(interaction, confession_id, "approved")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="confession:reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        confession_id = _confession_id_from_message(interaction.message, REVIEW_TITLE_PREFIX)
        if confession_id is None:
            await interaction.response.send_message("❌ This review message is invalid.", ephemeral=True)
            return
        await interaction.response.send_modal(RejectModal(confession_id))


async def submit_confession(interaction: discord.Interaction, message: str, parent_id: int | None = None) -> None:
    # Defer immediately: the anti-abuse checks below do several sequential
    # DB round-trips before we know what to say back, which can easily blow
    # past Discord's 3-second first-response window and invalidate the
    # interaction entirely ("Unknown interaction").
    await interaction.response.defer(ephemeral=True, thinking=True)

    if interaction.guild is None:
        await interaction.followup.send("❌ Confessions can only be submitted in a server.", ephemeral=True)
        return

    content = message.strip()
    if not content:
        await interaction.followup.send("❌ A confession cannot be empty.", ephemeral=True)
        return

    # 8.4 Mention abuse protection: neutralize @everyone/@here/user/role
    # mentions so they render as inert text instead of resolving.
    content = discord.utils.escape_mentions(content)

    session = get_session()
    try:
        restriction = await RestrictionRepository(session).get_active(interaction.guild.id, interaction.user.id)
        if restriction is not None:
            if restriction.expires_at:
                expiry = discord.utils.format_dt(restriction.expires_at.replace(tzinfo=timezone.utc), style="R")
                detail = f"Your confession access is restricted until {expiry}."
            else:
                detail = "Your confession access has been permanently restricted."
            if restriction.reason:
                detail += f"\nReason: {restriction.reason}"
            await interaction.followup.send(f"❌ {detail}", ephemeral=True)
            return

        servers = ServerRepository(session)
        server = await servers.get(interaction.guild.id)
        if server is None or not server.confession_channel_id:
            await interaction.followup.send("❌ This server has not configured a confession channel yet.", ephemeral=True)
            return
        if server.approval_enabled and not server.logging_channel_id:
            await interaction.followup.send("❌ Moderator approval is enabled, but no logging/review channel is configured. Ask an administrator to run `/config`.", ephemeral=True)
            return

        review_channel = None
        if server.approval_enabled:
            review_channel = interaction.guild.get_channel(server.logging_channel_id)
            if not isinstance(review_channel, discord.TextChannel):
                await interaction.followup.send("❌ The configured review channel is unavailable. Ask an administrator to reconfigure it.", ephemeral=True)
                return

        confessions = ConfessionRepository(session)

        # 8.1/8.2/8.3/8.7 anti-abuse checks
        block_reason = await evaluate_submission(confessions, server, interaction.user.id, content)
        if block_reason is not None:
            await interaction.followup.send(block_reason, ephemeral=True)
            return

        parent_confession = None
        if parent_id is not None:
            parent_confession = await confessions.get(parent_id, interaction.guild.id)
            if parent_confession is None:
                await interaction.followup.send("❌ The confession you're replying to no longer exists.", ephemeral=True)
                return

        reply_number = None
        if parent_confession is not None:
            reply_number = await servers.allocate_reply_number(interaction.guild.id)

        confession = await confessions.create(
            interaction.guild.id,
            interaction.user.id,
            content,
            "pending" if server.approval_enabled else "approved",
            parent_id=parent_confession.id if parent_confession else None,
            reply_number=reply_number,
        )
        await confessions.add_log(confession.id, "submitted", interaction.user.id)
        await record_and_check_burst(interaction.guild, server)

        if server.approval_enabled:
            role_mention = f"<@&{server.moderator_role_id}> " if server.moderator_role_id else ""
            sensitive = server.sensitive_content_detection and contains_sensitive_keywords(content)
            try:
                await review_channel.send(
                    role_mention,
                    embed=moderation_confession_embed(
                        confession.id, content, interaction.user,
                        parent_id=parent_confession.id if parent_confession else None,
                        reply_number=confession.reply_number,
                        theme=server.theme,
                        sensitive=sensitive,
                    ),
                    view=ModerationView(),
                    allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
                )
            except discord.HTTPException as error:
                await confessions.set_status(confession.id, "review_delivery_failed")
                await confessions.add_log(confession.id, "review_delivery_failed", details=str(error))
                await interaction.followup.send(f"⚠️ Your confession `#{confession.id}` was saved but could not reach moderators. Please contact an administrator.", ephemeral=True)
                return
            await send_moderation_log(interaction.guild, server, "submitted", confession, author=interaction.user)
            await interaction.followup.send(f"✅ Your confession was submitted anonymously as `#{confession.id}` and is awaiting review.", ephemeral=True)
        else:
            reference_message_id = parent_confession.public_message_id if parent_confession else None
            try:
                public_message = await post_public_confession(
                    interaction.guild, servers, server, confession.id, content,
                    parent_id=parent_confession.id if parent_confession else None,
                    reference_message_id=reference_message_id,
                    reply_number=confession.reply_number,
                )
                await confessions.set_public_message(confession.id, public_message.id)
                confession.public_message_id = public_message.id
            except (discord.HTTPException, ValueError) as error:
                await confessions.set_status(confession.id, "publication_failed")
                await confessions.add_log(confession.id, "publication_failed", details=str(error))
                await interaction.followup.send(f"⚠️ Your confession `#{confession.id}` was saved but could not be posted. Please contact a moderator.", ephemeral=True)
                return
            await send_moderation_log(interaction.guild, server, "posted", confession, author=interaction.user)
            await interaction.followup.send(f"✅ Your anonymous confession was posted as `#{confession.id}`.", ephemeral=True)
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def review_confession(interaction: discord.Interaction, confession_id: int, status: str, reason: str | None = None) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)

    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.followup.send("❌ Moderation is only available in a server.", ephemeral=True)
        return

    session = get_session()
    try:
        servers = ServerRepository(session)
        server = await servers.get(interaction.guild.id)
        if server is None or not can_moderate(interaction.user, server.moderator_role_id):
            await interaction.followup.send("❌ You do not have permission to moderate confessions.", ephemeral=True)
            return

        confessions = ConfessionRepository(session)
        confession = await confessions.get(confession_id, interaction.guild.id)
        if confession is None:
            await interaction.followup.send("❌ This confession no longer exists.", ephemeral=True)
            return
        if not await confessions.review(confession_id, interaction.guild.id, interaction.user.id, status, reason):
            await interaction.followup.send("ℹ️ This confession has already been reviewed.", ephemeral=True)
            return

        if status == "approved":
            reference_message_id = None
            if confession.parent_id:
                parent_confession = await confessions.get(confession.parent_id, interaction.guild.id)
                if parent_confession and parent_confession.public_message_id:
                    reference_message_id = parent_confession.public_message_id
            try:
                public_message = await post_public_confession(
                    interaction.guild, servers, server, confession.id, confession.content,
                    parent_id=confession.parent_id,
                    reference_message_id=reference_message_id,
                    reply_number=confession.reply_number,
                )
                await confessions.set_public_message(confession.id, public_message.id)
                confession.public_message_id = public_message.id
            except (discord.HTTPException, ValueError) as error:
                await confessions.set_status(confession.id, "publication_failed")
                await confessions.add_log(confession.id, "publication_failed", interaction.user.id, str(error))
                await interaction.followup.send("⚠️ Approved, but it could not be posted. Check the confession channel and bot permissions.", ephemeral=True)
                if interaction.message:
                    await interaction.message.edit(view=None)
                return

        action = "approved" if status == "approved" else "rejected"
        await confessions.add_log(confession.id, action, interaction.user.id, reason)

        author = interaction.guild.get_member(confession.author_id)
        if author is None:
            try:
                author = await interaction.client.fetch_user(confession.author_id)
            except discord.HTTPException:
                author = None

        await send_moderation_log(
            interaction.guild, server, action, confession,
            author=author, moderator=interaction.user, reason=reason,
        )
        await interaction.followup.send(f"✅ Confession #{confession.id} {action}.", ephemeral=True)
        if interaction.message:
            await interaction.message.edit(view=None)
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def delete_confession(interaction: discord.Interaction, confession_id: int, reason: str) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)

    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.followup.send("❌ Moderation is only available in a server.", ephemeral=True)
        return

    session = get_session()
    try:
        servers = ServerRepository(session)
        server = await servers.get(interaction.guild.id)
        if server is None or not can_moderate(interaction.user, server.moderator_role_id):
            await interaction.followup.send("❌ You do not have permission to delete confessions.", ephemeral=True)
            return

        confessions = ConfessionRepository(session)
        confession = await confessions.get(confession_id, interaction.guild.id)
        if confession is None:
            await interaction.followup.send("❌ This confession no longer exists.", ephemeral=True)
            return
        if confession.status != "approved":
            await interaction.followup.send(f"❌ Only posted confessions can be deleted (current status: {confession.status}).", ephemeral=True)
            return

        if confession.public_message_id and server.confession_channel_id:
            channel = interaction.guild.get_channel(server.confession_channel_id)
            if isinstance(channel, discord.TextChannel):
                try:
                    await channel.get_partial_message(confession.public_message_id).delete()
                except discord.HTTPException:
                    pass

        await confessions.set_status(confession_id, "deleted")
        confession.status = "deleted"
        await confessions.add_log(confession_id, "deleted", interaction.user.id, reason)

        author = interaction.guild.get_member(confession.author_id)
        if author is None:
            try:
                author = await interaction.client.fetch_user(confession.author_id)
            except discord.HTTPException:
                author = None

        await send_moderation_log(
            interaction.guild, server, "deleted", confession,
            author=author, moderator=interaction.user, reason=reason,
        )
        await interaction.followup.send(f"✅ Confession #{confession_id} deleted.", ephemeral=True)
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


class Confession(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="confess", description="Submit an anonymous confession.")
    @app_commands.describe(message="Your confession (up to 2,000 characters)")
    async def confess(self, interaction: discord.Interaction, message: app_commands.Range[str, 1, 2000]) -> None:
        await submit_confession(interaction, message)

    @app_commands.command(name="confession-status", description="Check the status of one of your confessions.")
    @app_commands.describe(confession_id="The anonymous confession ID")
    async def confession_status(self, interaction: discord.Interaction, confession_id: int) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        session = get_session()
        try:
            confession = await ConfessionRepository(session).get_for_author(confession_id, interaction.guild.id, interaction.user.id)
            if confession is None:
                await interaction.response.send_message("❌ No confession with that ID belongs to you.", ephemeral=True)
                return
            labels = {
                "pending": "⏳ Awaiting moderator review",
                "approved": "✅ Posted anonymously",
                "rejected": "❌ Rejected",
                "publication_failed": "⚠️ Approved but could not be posted",
                "review_delivery_failed": "⚠️ Saved but could not reach moderators",
                "deleted": "🗑️ Removed by a moderator",
            }
            response = f"Confession `#{confession.id}`: {labels.get(confession.status, confession.status)}"
            if confession.reply_number is not None:
                response += f"\nShown publicly as: Anonymous Reply #{confession.reply_number}"
            if confession.status == "rejected" and confession.rejection_reason:
                response += f"\nReason: {confession.rejection_reason}"
            await interaction.response.send_message(response, ephemeral=True)
        finally:
            await session.close()


async def setup(bot: commands.Bot):
    await bot.add_cog(Confession(bot))