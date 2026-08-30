from datetime import timezone

import discord

from bot.database.models import Confession, Server
from bot.utils.embeds import theme_color


ACTION_TITLES = {
    "submitted": "📝 New Confession Submitted",
    "posted": "📬 Confession Posted",
    "approved": "✅ Confession Approved",
    "rejected": "❌ Confession Rejected",
}


def _build_log_embed(
    guild: discord.Guild,
    server: Server,
    action: str,
    confession: Confession,
    author: discord.abc.User | None,
    moderator: discord.abc.User | None,
    reason: str | None,
) -> tuple[discord.Embed, discord.ui.View | None]:
    embed = discord.Embed(title=ACTION_TITLES.get(action, action.title()), color=theme_color(server.theme))

    if author is not None:
        submitter_value = f"||{author} (`{author.id}`)||"
    else:
        submitter_value = f"||Unknown user (`{confession.author_id}`)||"
    embed.add_field(name="Submitted by", value=submitter_value, inline=False)

    content = confession.content if len(confession.content) <= 1024 else confession.content[:1021] + "..."
    embed.add_field(name="Confession", value=content, inline=False)

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
    if confession.public_message_id and server.confession_channel_id:
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
    """Best-effort audit-channel output; database logging remains authoritative."""
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
    except discord.HTTPException:
        pass