from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_session
from bot.database.repository import ConfessionRepository, ServerRepository
from bot.utils.embeds import theme_color, theme_label


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="View this server's confession statistics.")
    async def stats(self, interaction: discord.Interaction) -> None:
        # Several sequential DB queries follow — defer up front so we don't
        # risk missing Discord's 3-second first-response window.
        await interaction.response.defer()

        if interaction.guild is None:
            await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None:
                await interaction.followup.send("ℹ️ This server hasn't been configured yet.", ephemeral=True)
                return

            confessions = ConfessionRepository(session)
            total_confessions, total_replies = await confessions.count_confessions_and_replies(interaction.guild.id)
            counts = await confessions.count_by_status(interaction.guild.id)
            now = datetime.utcnow()
            last_24h = await confessions.count_since(interaction.guild.id, now - timedelta(hours=24))
            last_7d = await confessions.count_since(interaction.guild.id, now - timedelta(days=7))
        finally:
            await session.close()

        embed = discord.Embed(title="📊 Confession Statistics", color=theme_color(server.theme))
        embed.add_field(name="Total Confessions", value=str(total_confessions), inline=True)
        embed.add_field(name="Total Replies", value=str(total_replies), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="✅ Approved", value=str(counts.get("approved", 0)), inline=True)
        embed.add_field(name="❌ Rejected", value=str(counts.get("rejected", 0)), inline=True)
        embed.add_field(name="⏳ Pending", value=str(counts.get("pending", 0)), inline=True)
        embed.add_field(name="Last 24 hours", value=str(last_24h), inline=True)
        embed.add_field(name="Last 7 days", value=str(last_7d), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Approval Required", value="✅ Yes" if server.approval_enabled else "❌ No", inline=True)
        embed.add_field(name="Theme", value=theme_label(server.theme), inline=True)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="privacy", description="See what data this bot stores about confessions.")
    async def privacy(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="🔒 Privacy & Data",
            description=(
                "This bot stores only what's needed to run the confession system:\n\n"
                "• Your Discord user ID and the text of anything you submit\n"
                "• Timestamps for when things were submitted/reviewed\n\n"
                "**Who can see your identity:** only server moderators, and only when reviewing "
                "or investigating a confession — your username is never shown in the public "
                "confession channel. Moderator-facing logs keep your name behind a spoiler tag "
                "so it isn't shown by accident.\n\n"
                "We don't store usernames, avatars, or any message history beyond the confession "
                "text itself."
            ),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))