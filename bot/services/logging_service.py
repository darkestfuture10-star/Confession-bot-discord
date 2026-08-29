import discord

from bot.database.models import Server


async def send_moderation_log(guild: discord.Guild, server: Server, message: str) -> None:
    """Best-effort audit-channel output; database logging remains authoritative."""
    if not server.logging_enabled or not server.logging_channel_id:
        return
    channel = guild.get_channel(server.logging_channel_id)
    if isinstance(channel, discord.TextChannel):
        await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
