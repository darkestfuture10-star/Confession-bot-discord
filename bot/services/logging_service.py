import logging
from datetime import timezone

import discord

from bot.database.models import Confession, Server
from bot.utils.embeds import theme_color


logger = logging.getLogger("confession_bot.logging_service")


ACTION_TEMPLATES = {
    "submitted": ("📝", "New {noun} Submitted"),
    "posted": ("📬", "{noun} Posted"),
    "approved": ("✅", "{noun} Approved"),
    "rejected": ("❌", "{noun} Rejected"),
    "deleted": ("🗑️", "{noun} Deleted"),
}


def _title_for(action: str, confession: Confession) -> str:
    noun = "Reply" if confession.parent_id else "Confession"
    emoji, template = ACTION_TEMPLATES.get(action, ("", "{noun} " + action.title()))
    text = template.format(noun=noun)
    return f"{emoji} {text}" if emoji else text


def _build_log_embed(
    guild: discord.Guild,
    server: Server,
    action: str,
    confession: Confession,
    author: discord.abc.User | None,
    moderator: discord.abc.User | None,
    reason: str | None,
) -> tuple[discord.Embed, discord.ui.View | None]:
    embed = discord.Embed(title=_title_for(action, confession), color=theme_color(server.theme))

    if author is not None:
        submitter_value = f"||{author.mention} (`{author.id}`)||"
    else:
        submitter_value = f"||<@{confession.author_id}> (`{confession.author_id}`)||"
    embed.add_field(name="Submitted by", value=submitter_value, inline=False)

    content = confession.content if len(confession.content) <= 1024 else confession.content[:1021] + "..."
    embed.add_field(name="Confession" if not confession.parent_id else "Reply", value=content, inline=False)

    embed.add_field(
        name="Submitted",
        value=discord.utils.format_dt(confession.submitted_at.replace(tzinfo=timezone.utc), style="F"),
        inline=True,
    )

    if moderator is not None:
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)

    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)

    embed.set_footer(text=f"Confession #{confession.id}")

    view = None
    # No point linking to a message that's just been deleted.
    if action != "deleted" and confession.public_message_id and server.confession_channel_id:
        url = f"https://discord.com/channels/{guild.id}/{server.confession_channel_id}/{confession.public_message_id}"
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="View Confession", style=discord.ButtonStyle.link, url=url))

    return embed, view


async def send_moderation_log(
    guild: discord.Guild,
    server: Server,
    action: str,
    confession: Confession,
    *,
    author: discord.abc.User | None = None,
    moderator: discord.abc.User | None = None,
    reason: str | None = None,
) -> None:
    """Best-effort audit-channel output for a specific confession's lifecycle event."""
    if not server.logging_enabled or not server.logging_channel_id:
        return
    channel = guild.get_channel(server.logging_channel_id)
    if not isinstance(channel, discord.TextChannel):
        return

    embed, view = _build_log_embed(guild, server, action, confession, author, moderator, reason)
    try:
        if view is not None:
            await channel.send(embed=embed, view=view)
        else:
            await channel.send(embed=embed)
    except discord.HTTPException as error:
        # The audit record itself already landed in the database via add_log()
        # elsewhere — this is only the Discord-channel notification failing.
        # Silently dropping it would leave you with zero trace of the failure,
        # so surface it in the console/log file even though we can't retry here.
        logger.warning(
            "Failed to deliver moderation log (%s) for confession #%s in guild %s: %s",
            action, confession.id, guild.id, error,
        )


async def send_event_log(
    guild: discord.Guild,
    server: Server,
    title: str,
    *,
    description: str | None = None,
    fields: list[tuple[str, str]] | None = None,
    footer: str | None = None,
) -> None:
    """Best-effort audit-channel output for events not tied to a single
    confession (e.g. user restrictions)."""
    if not server.logging_enabled or not server.logging_channel_id:
        return
    channel = guild.get_channel(server.logging_channel_id)
    if not isinstance(channel, discord.TextChannel):
        return

    embed = discord.Embed(title=title, description=description, color=theme_color(server.theme))
    for name, value in (fields or []):
        embed.add_field(name=name, value=value, inline=False)
    if footer:
        embed.set_footer(text=footer)

    try:
        await channel.send(embed=embed)
    except discord.HTTPException as error:
        logger.warning(
            "Failed to deliver event log (%s) in guild %s: %s",
            title, guild.id, error,
        )