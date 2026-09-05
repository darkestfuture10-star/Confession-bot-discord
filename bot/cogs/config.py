import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_session
from bot.database.repository import ServerRepository
from bot.utils.embeds import THEMES, theme_color, theme_label


async def build_config_embed(guild: discord.Guild, server) -> discord.Embed:
    confession_channel = "Not configured"
    if server.confession_channel_id:
        channel = guild.get_channel(server.confession_channel_id)
        if channel:
            confession_channel = channel.mention

    moderator_role = "Not configured"
    if server.moderator_role_id:
        role = guild.get_role(server.moderator_role_id)
        if role:
            moderator_role = role.mention

    approval_status = "✅ Enabled" if server.approval_enabled else "❌ Disabled"
    logging_status = "✅ Enabled" if server.logging_enabled else "❌ Disabled"

    logging_channel = "Not configured"
    if server.logging_channel_id:
        channel = guild.get_channel(server.logging_channel_id)
        if channel:
            logging_channel = channel.mention

    embed = discord.Embed(
        title="⚙️ Confession Bot Configuration",
        description="Use the buttons below to configure the confession system.",
        color=theme_color(server.theme),
    )
    embed.add_field(name="Confession Channel", value=confession_channel, inline=False)
    embed.add_field(name="Moderator Role", value=moderator_role, inline=False)
    embed.add_field(name="Approval", value=approval_status, inline=True)
    embed.add_field(name="Logging", value=logging_status, inline=True)
    embed.add_field(name="Logging Channel", value=logging_channel, inline=False)
    embed.add_field(name="Theme", value=theme_label(server.theme), inline=True)
    embed.add_field(
        name="Sensitive Content Alerts",
        value="✅ Enabled" if server.sensitive_content_detection else "❌ Disabled",
        inline=True,
    )
    return embed


async def refresh_panel(panel_message: discord.Message | None, guild: discord.Guild, server) -> None:
    """Best-effort live update of the original /config panel message."""
    if panel_message is None:
        return
    try:
        embed = await build_config_embed(guild, server)
        await panel_message.edit(embed=embed, view=ConfigView(panel_message))
    except discord.HTTPException:
        pass


class ConfessionChannelView(discord.ui.View):
    def __init__(self, panel_message: discord.Message | None = None):
        super().__init__(timeout=60)
        self.panel_message = panel_message

        self.channel_select = discord.ui.ChannelSelect(
            placeholder="Select a confession channel",
            channel_types=[discord.ChannelType.text],
        )
        self.channel_select.callback = self.select_channel
        self.add_item(self.channel_select)

    async def select_channel(self, interaction: discord.Interaction):
        channel = self.channel_select.values[0]

        if interaction.guild is None:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            repository = ServerRepository(session)
            server = await repository.set_confession_channel(interaction.guild.id, channel.id)
        except Exception:
            await session.rollback()
            await interaction.response.send_message("❌ Failed to save the confession channel.", ephemeral=True)
            raise
        finally:
            await session.close()

        await refresh_panel(self.panel_message, interaction.guild, server)
        await interaction.response.send_message(f"✅ Confession channel set to {channel.mention}.", ephemeral=True)


class ModeratorRoleView(discord.ui.View):
    def __init__(self, panel_message: discord.Message | None = None):
        super().__init__(timeout=60)
        self.panel_message = panel_message

        self.role_select = discord.ui.RoleSelect(placeholder="Select the moderator role")
        self.role_select.callback = self.select_role
        self.add_item(self.role_select)

    async def select_role(self, interaction: discord.Interaction):
        role = self.role_select.values[0]

        if interaction.guild is None:
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            repository = ServerRepository(session)
            server = await repository.set_moderator_role(interaction.guild.id, role.id)
        except Exception:
            await session.rollback()
            await interaction.response.send_message("❌ Failed to save the moderator role.", ephemeral=True)
            raise
        finally:
            await session.close()

        await refresh_panel(self.panel_message, interaction.guild, server)
        await interaction.response.send_message(f"✅ Moderator role set to {role.mention}.", ephemeral=True)


class ApprovalView(discord.ui.View):
    def __init__(self, panel_message: discord.Message | None = None):
        super().__init__(timeout=60)
        self.panel_message = panel_message

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success)
    async def enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_approval(interaction, True)

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger)
    async def disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_approval(interaction, False)

    async def set_approval(self, interaction: discord.Interaction, enabled: bool):
        if interaction.guild is None:
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            repository = ServerRepository(session)
            server = await repository.set_approval(interaction.guild.id, enabled)
        except Exception:
            await session.rollback()
            await interaction.response.send_message("❌ Failed to update approval settings.", ephemeral=True)
            raise
        finally:
            await session.close()

        await refresh_panel(self.panel_message, interaction.guild, server)
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(f"✅ Moderator approval {status}.", ephemeral=True)


class LoggingView(discord.ui.View):
    def __init__(self, panel_message: discord.Message | None = None):
        super().__init__(timeout=60)
        self.panel_message = panel_message

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success)
    async def enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_logging(interaction, True)

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger)
    async def disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_logging(interaction, False)

    async def set_logging(self, interaction: discord.Interaction, enabled: bool):
        if interaction.guild is None:
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            repository = ServerRepository(session)
            server = await repository.set_logging(interaction.guild.id, enabled)
        except Exception:
            await session.rollback()
            await interaction.response.send_message("❌ Failed to update logging settings.", ephemeral=True)
            raise
        finally:
            await session.close()

        await refresh_panel(self.panel_message, interaction.guild, server)
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(f"✅ Logging {status}.", ephemeral=True)


class LoggingChannelView(discord.ui.View):
    def __init__(self, panel_message: discord.Message | None = None):
        super().__init__(timeout=60)
        self.panel_message = panel_message

        self.channel_select = discord.ui.ChannelSelect(
            placeholder="Select a logging channel",
            channel_types=[discord.ChannelType.text],
        )
        self.channel_select.callback = self.select_channel
        self.add_item(self.channel_select)

    async def select_channel(self, interaction: discord.Interaction):
        channel = self.channel_select.values[0]

        if interaction.guild is None:
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            repository = ServerRepository(session)
            server = await repository.set_logging_channel(interaction.guild.id, channel.id)
        except Exception:
            await session.rollback()
            await interaction.response.send_message("❌ Failed to save the logging channel.", ephemeral=True)
            raise
        finally:
            await session.close()

        await refresh_panel(self.panel_message, interaction.guild, server)
        await interaction.response.send_message(f"✅ Logging channel set to {channel.mention}.", ephemeral=True)


class ThemeView(discord.ui.View):
    def __init__(self, panel_message: discord.Message | None = None):
        super().__init__(timeout=60)
        self.panel_message = panel_message

        self.theme_select = discord.ui.Select(
            placeholder="Select a theme",
            options=[
                discord.SelectOption(label=data["label"], value=key, emoji=data["emoji"])
                for key, data in THEMES.items()
            ],
        )
        self.theme_select.callback = self.select_theme
        self.add_item(self.theme_select)

    async def select_theme(self, interaction: discord.Interaction):
        theme = self.theme_select.values[0]

        if interaction.guild is None:
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            repository = ServerRepository(session)
            server = await repository.set_theme(interaction.guild.id, theme)
        except Exception:
            await session.rollback()
            await interaction.response.send_message("❌ Failed to save the theme.", ephemeral=True)
            raise
        finally:
            await session.close()

        await refresh_panel(self.panel_message, interaction.guild, server)
        await interaction.response.send_message(f"✅ Theme set to **{theme_label(theme)}**.", ephemeral=True)


class ConfigView(discord.ui.View):
    def __init__(self, panel_message: discord.Message | None = None):
        super().__init__(timeout=300)
        self.panel_message = panel_message

    @discord.ui.button(label="Confession Channel", style=discord.ButtonStyle.primary)
    async def confession_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Select the confession channel below.", view=ConfessionChannelView(self.panel_message), ephemeral=True)

    @discord.ui.button(label="Moderator Role", style=discord.ButtonStyle.primary)
    async def moderator_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Select the moderator role below.", view=ModeratorRoleView(self.panel_message), ephemeral=True)

    @discord.ui.button(label="Sensitive Content Alerts", style=discord.ButtonStyle.secondary)
    async def sensitive_detection(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Choose whether confessions matching sensitive/crisis keywords get flagged for moderators during review.",
            view=SensitiveDetectionView(self.panel_message),
            ephemeral=True,
        )

    @discord.ui.button(label="Approval", style=discord.ButtonStyle.secondary)
    async def approval(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Choose whether confessions require moderator approval.", view=ApprovalView(self.panel_message), ephemeral=True)

    @discord.ui.button(label="Logging", style=discord.ButtonStyle.secondary)
    async def logging(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Choose whether confession logging is enabled.", view=LoggingView(self.panel_message), ephemeral=True)

    @discord.ui.button(label="Logging Channel", style=discord.ButtonStyle.secondary)
    async def logging_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Select the logging channel below.", view=LoggingChannelView(self.panel_message), ephemeral=True)

    @discord.ui.button(label="Theme", style=discord.ButtonStyle.secondary)
    async def theme(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Choose a color theme for confession embeds.", view=ThemeView(self.panel_message), ephemeral=True)

class SensitiveDetectionView(discord.ui.View):
    def __init__(self, panel_message: discord.Message | None = None):
        super().__init__(timeout=60)
        self.panel_message = panel_message

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success)
    async def enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_detection(interaction, True)

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger)
    async def disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_detection(interaction, False)

    async def set_detection(self, interaction: discord.Interaction, enabled: bool):
        if interaction.guild is None:
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            repository = ServerRepository(session)
            server = await repository.set_sensitive_detection(interaction.guild.id, enabled)
        except Exception:
            await session.rollback()
            await interaction.response.send_message("❌ Failed to update this setting.", ephemeral=True)
            raise
        finally:
            await session.close()

        await refresh_panel(self.panel_message, interaction.guild, server)
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(f"✅ Sensitive content detection {status}.", ephemeral=True)

class Config(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="config", description="Configure the confession bot for this server.")
    @app_commands.default_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need Administrator permission to use this command.", ephemeral=True)
            return

        if interaction.guild is None:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            repository = ServerRepository(session)
            server = await repository.get_or_create(interaction.guild.id)
        finally:
            await session.close()

        embed = await build_config_embed(interaction.guild, server)
        await interaction.response.send_message(embed=embed, view=ConfigView(), ephemeral=True)

        # Bind the panel to its own message so sub-panels can refresh it live.
        panel_message = await interaction.original_response()
        await panel_message.edit(view=ConfigView(panel_message))


async def setup(bot: commands.Bot):
    await bot.add_cog(Config(bot))