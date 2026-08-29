import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_session
from bot.database.repository import ConfessionRepository, ServerRepository
from bot.services.logging_service import send_moderation_log
from bot.utils.embeds import moderation_confession_embed, public_confession_embed
from bot.utils.permissions import can_moderate


async def post_public_confession(guild: discord.Guild, channel_id: int | None, confession_id: int, content: str) -> discord.Message:
    channel = guild.get_channel(channel_id) if channel_id else None
    if not isinstance(channel, discord.TextChannel):
        raise ValueError("The configured confession channel is missing or is not a text channel.")
    return await channel.send(embed=public_confession_embed(confession_id, content))


class RejectModal(discord.ui.Modal, title="Reject confession"):
    reason = discord.ui.TextInput(label="Reason (optional)", required=False, max_length=500, style=discord.TextStyle.paragraph)

    def __init__(self, confession_id: int):
        super().__init__()
        self.confession_id = confession_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await review_confession(interaction, self.confession_id, "rejected", str(self.reason) or None)


class ModerationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @staticmethod
    def confession_id_from_message(message: discord.Message | None) -> int | None:
        if not message or not message.embeds or not message.embeds[0].title:
            return None
        title = message.embeds[0].title
        prefix = "Confession #"
        if not title.startswith(prefix):
            return None
        try:
            return int(title.removeprefix(prefix).split()[0])
        except ValueError:
            return None

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="confession:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        confession_id = self.confession_id_from_message(interaction.message)
        if confession_id is None:
            await interaction.response.send_message("❌ This review message is invalid.", ephemeral=True)
            return
        await review_confession(interaction, confession_id, "approved")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="confession:reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        confession_id = self.confession_id_from_message(interaction.message)
        if confession_id is None:
            await interaction.response.send_message("❌ This review message is invalid.", ephemeral=True)
            return
        await interaction.response.send_modal(RejectModal(confession_id))


async def review_confession(interaction: discord.Interaction, confession_id: int, status: str, reason: str | None = None) -> None:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("❌ Moderation is only available in a server.", ephemeral=True)
        return

    session = get_session()
    try:
        servers = ServerRepository(session)
        server = await servers.get(interaction.guild.id)
        if server is None or not can_moderate(interaction.user, server.moderator_role_id):
            await interaction.response.send_message("❌ You do not have permission to moderate confessions.", ephemeral=True)
            return

        confessions = ConfessionRepository(session)
        confession = await confessions.get(confession_id, interaction.guild.id)
        if confession is None:
            await interaction.response.send_message("❌ This confession no longer exists.", ephemeral=True)
            return
        if not await confessions.review(confession_id, interaction.guild.id, interaction.user.id, status, reason):
            await interaction.response.send_message("ℹ️ This confession has already been reviewed.", ephemeral=True)
            return

        if status == "approved":
            try:
                public_message = await post_public_confession(interaction.guild, server.confession_channel_id, confession.id, confession.content)
                await confessions.set_public_message(confession.id, public_message.id)
            except (discord.HTTPException, ValueError) as error:
                await confessions.set_status(confession.id, "publication_failed")
                await confessions.add_log(confession.id, "publication_failed", interaction.user.id, str(error))
                await interaction.response.send_message("⚠️ Approved, but it could not be posted. Check the confession channel and bot permissions.", ephemeral=True)
                if interaction.message:
                    await interaction.message.edit(view=None)
                return

        action = "approved" if status == "approved" else "rejected"
        await confessions.add_log(confession.id, action, interaction.user.id, reason)
        await send_moderation_log(interaction.guild, server, f"Confession #{confession.id} was **{action}** by {interaction.user.mention}.")
        await interaction.response.send_message(f"✅ Confession #{confession.id} {action}.", ephemeral=True)
        if interaction.message:
            await interaction.message.edit(view=None)
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
        if interaction.guild is None:
            await interaction.response.send_message("❌ Confessions can only be submitted in a server.", ephemeral=True)
            return

        content = message.strip()
        if not content:
            await interaction.response.send_message("❌ A confession cannot be empty.", ephemeral=True)
            return

        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not server.confession_channel_id:
                await interaction.response.send_message("❌ This server has not configured a confession channel yet.", ephemeral=True)
                return
            if server.approval_enabled and not server.logging_channel_id:
                await interaction.response.send_message("❌ Moderator approval is enabled, but no logging/review channel is configured. Ask an administrator to run `/config`.", ephemeral=True)
                return
            review_channel = None
            if server.approval_enabled:
                review_channel = interaction.guild.get_channel(server.logging_channel_id)
                if not isinstance(review_channel, discord.TextChannel):
                    await interaction.response.send_message("❌ The configured review channel is unavailable. Ask an administrator to reconfigure it.", ephemeral=True)
                    return

            confessions = ConfessionRepository(session)
            confession = await confessions.create(interaction.guild.id, interaction.user.id, content, "pending" if server.approval_enabled else "approved")
            await confessions.add_log(confession.id, "submitted", interaction.user.id)

            if server.approval_enabled:
                role_mention = f"<@&{server.moderator_role_id}> " if server.moderator_role_id else ""
                try:
                    await review_channel.send(
                        role_mention,
                        embed=moderation_confession_embed(confession.id, content, interaction.user),
                        view=ModerationView(),
                        allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
                    )
                except discord.HTTPException as error:
                    await confessions.set_status(confession.id, "review_delivery_failed")
                    await confessions.add_log(confession.id, "review_delivery_failed", details=str(error))
                    await interaction.response.send_message(f"⚠️ Your confession `#{confession.id}` was saved but could not reach moderators. Please contact an administrator.", ephemeral=True)
                    return
                await interaction.response.send_message(f"✅ Your confession was submitted anonymously as `#{confession.id}` and is awaiting review.", ephemeral=True)
            else:
                try:
                    public_message = await post_public_confession(interaction.guild, server.confession_channel_id, confession.id, content)
                    await confessions.set_public_message(confession.id, public_message.id)
                except (discord.HTTPException, ValueError) as error:
                    await confessions.set_status(confession.id, "publication_failed")
                    await confessions.add_log(confession.id, "publication_failed", details=str(error))
                    await interaction.response.send_message(f"⚠️ Your confession `#{confession.id}` was saved but could not be posted. Please contact a moderator.", ephemeral=True)
                    return
                await send_moderation_log(interaction.guild, server, f"Confession #{confession.id} was posted automatically.")
                await interaction.response.send_message(f"✅ Your anonymous confession was posted as `#{confession.id}`.", ephemeral=True)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

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
            }
            response = f"Confession `#{confession.id}`: {labels.get(confession.status, confession.status)}"
            if confession.status == "rejected" and confession.rejection_reason:
                response += f"\nReason: {confession.rejection_reason}"
            await interaction.response.send_message(response, ephemeral=True)
        finally:
            await session.close()


async def setup(bot: commands.Bot):
    await bot.add_cog(Confession(bot))
