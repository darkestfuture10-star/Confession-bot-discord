import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_session
from bot.database.repository import ServerRepository


class ConfessionChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

        self.channel_select = discord.ui.ChannelSelect(
            placeholder="Select a confession channel",
            channel_types=[discord.ChannelType.text],
        )

        self.channel_select.callback = self.select_channel
        self.add_item(self.channel_select)

    async def select_channel(
        self,
        interaction: discord.Interaction,
    ):
        channel = self.channel_select.values[0]

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        session = get_session()

        try:
            repository = ServerRepository(session)

            await repository.set_confession_channel(
                interaction.guild.id,
                channel.id,
            )

        except Exception:
            await session.rollback()

            await interaction.response.send_message(
                "❌ Failed to save the confession channel.",
                ephemeral=True,
            )

            raise

        finally:
            await session.close()

        await interaction.response.send_message(
            f"✅ Confession channel set to {channel.mention}.",
            ephemeral=True,
        )


class ModeratorRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

        self.role_select = discord.ui.RoleSelect(
            placeholder="Select the moderator role",
        )

        self.role_select.callback = self.select_role
        self.add_item(self.role_select)

    # Select

    async def select_role(
        self,
        interaction: discord.Interaction,
    ):
        role = self.role_select.values[0]

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This can only be used in a server.",
                ephemeral=True,
            )
            return

        session = get_session()

        try:
            repository = ServerRepository(session)

            await repository.set_moderator_role(
                interaction.guild.id,
                role.id,
            )

        except Exception:
            await session.rollback()

            await interaction.response.send_message(
                "❌ Failed to save the moderator role.",
                ephemeral=True,
            )

            raise

        finally:
            await session.close()

        await interaction.response.send_message(
            f"✅ Moderator role set to {role.mention}.",
            ephemeral=True,
        )


class ConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    # Button

    @discord.ui.button(
        label="Confession Channel",
        style=discord.ButtonStyle.primary,
    )
    async def confession_channel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "Select the confession channel below.",
            view=ConfessionChannelView(),
            ephemeral=True,
        )

    # Button

    @discord.ui.button(
        label="Moderator Role",
        style=discord.ButtonStyle.primary,
    )
    async def moderator_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "Select the moderator role below.",
            view=ModeratorRoleView(),
            ephemeral=True,
        )

    # Button

    @discord.ui.button(
        label="Approval",
        style=discord.ButtonStyle.secondary,
    )
    async def approval(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "Approval configuration coming next.",
            ephemeral=True,
        )

    # Button

    @discord.ui.button(
        label="Logging",
        style=discord.ButtonStyle.secondary,
    )
    async def logging(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "Logging configuration coming next.",
            ephemeral=True,
        )

    # Button

    @discord.ui.button(
        label="Logging Channel",
        style=discord.ButtonStyle.secondary,
    )
    async def logging_channel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "Logging channel configuration coming next.",
            ephemeral=True,
        )

    # Button

    @discord.ui.button(
        label="Theme",
        style=discord.ButtonStyle.secondary,
    )
    async def theme(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "Theme configuration coming next.",
            ephemeral=True,
        )


class Config(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Command

    @app_commands.command(
        name="config",
        description="Configure the confession bot for this server.",
    )
    @app_commands.default_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need Administrator permission to use this command.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        session = get_session()

        try:
            repository = ServerRepository(session)

            server = await repository.get_or_create(
                interaction.guild.id
            )

            confession_channel = "Not configured"

            if server.confession_channel_id:
                channel = interaction.guild.get_channel(
                    server.confession_channel_id
                )

                if channel:
                    confession_channel = channel.mention

            moderator_role = "Not configured"

            if server.moderator_role_id:
                role = interaction.guild.get_role(
                    server.moderator_role_id
                )

                if role:
                    moderator_role = role.mention

        finally:
            await session.close()

        embed = discord.Embed(
            title="⚙️ Confession Bot Configuration",
            description=(
                "Use the buttons below to configure "
                "the confession system."
            ),
        )

        embed.add_field(
            name="Confession Channel",
            value=confession_channel,
            inline=False,
        )

        embed.add_field(
            name="Moderator Role",
            value=moderator_role,
            inline=False,
        )

        embed.add_field(
            name="Approval",
            value="✅ Enabled",
            inline=True,
        )

        embed.add_field(
            name="Logging",
            value="✅ Enabled",
            inline=True,
        )

        embed.add_field(
            name="Logging Channel",
            value="Not configured",
            inline=False,
        )

        embed.add_field(
            name="Theme",
            value="Default",
            inline=True,
        )

        await interaction.response.send_message(
            embed=embed,
            view=ConfigView(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Config(bot))