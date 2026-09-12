import discord
from discord import app_commands
from discord.ext import commands

from bot.config.settings import FEEDBACK_FORM_URL
from bot.database.connection import get_session
from bot.database.repository import ServerRepository
from bot.utils.embeds import theme_color


HELP_SECTIONS = [
    {
        "label": "Overview",
        "emoji": "📖",
        "title": "Anonymous Confessions",
        "description": (
            "This bot lets anyone in this server post fully anonymous confessions "
            "and replies, with an optional moderator review step before anything "
            "goes public.\n\n"
            "**Quick command list**\n"
            "`/confess` · `/confession-status` · `/stats`\n\n"
            "Use the menu below, or the ◀ ▶ buttons, to browse this guide."
        ),
    },
    {
        "label": "Confessing",
        "emoji": "📝",
        "title": "Submitting a Confession",
        "description": (
            "**/confess** `<message>` — submit an anonymous confession (up to 2,000 characters).\n\n"
            "• Your identity is never shown publicly — only moderators can see who "
            "submitted something, and only while reviewing it.\n"
            "• A short cooldown applies between submissions, plus an hourly limit, "
            "to keep things spam-free.\n"
            "• Any @mentions you include are automatically neutralized so they "
            "can't tag or ping anyone.\n"
            "• The newest confession in the channel also carries a "
            "**📝 Submit a Confession** button as a shortcut."
        ),
    },
    {
        "label": "Replying",
        "emoji": "💬",
        "title": "Replying to a Confession",
        "description": (
            "Every confession has a **💬 Reply** button. Replies get their own "
            "separate numbering — *Anonymous Reply #1, #2, ...* — so they're "
            "easy to tell apart from top-level confessions.\n\n"
            "Replies go through the same review process as regular confessions "
            "when moderator approval is enabled, and appear threaded under the "
            "original message once posted."
        ),
    },
    {
        "label": "Checking",
        "emoji": "🔍",
        "title": "Checking Status",
        "description": (
            "**/confession-status** `<id>` — check whether one of your own "
            "confessions is pending, approved, or rejected.\n\n"
            "**/stats** — this server's confession totals, approval breakdown, "
            "and recent activity."
        ),
    },
    {
        "label": "Privacy",
        "emoji": "🔒",
        "title": "Privacy & Data",
        "description": (
            "This bot stores only what's needed to run the confession system:\n\n"
            "• Your Discord user ID and the text of anything you submit\n"
            "• Timestamps for when things were submitted/reviewed\n\n"
            "**Who can see your identity:** only server moderators, and only when "
            "reviewing or investigating a confession — your username is never shown "
            "in the public confession channel. Moderator-facing logs keep your name "
            "behind a spoiler tag so it isn't shown by accident.\n\n"
            "We don't store usernames, avatars, or any message history beyond the "
            "confession text itself."
        ),
    },
    {
        "label": "For Moderators",
        "emoji": "🛡️",
        "title": "Moderator Tools",
        "description": (
            "These commands require the **Manage Messages** permission (or being "
            "the server owner):\n\n"
            "**/moderation-panel** — the review queue, 🗑️ Delete a posted "
            "confession, 🔨 Restrict / 🔓 Unrestrict a user, ⏱️ Waive a user's "
            "cooldown.\n\n"
            "**/moderator-dashboard** — live stats, 🔍 search a confession's "
            "audit log, 👥 list restricted users, 🔧 check the bot's channel "
            "permissions, 👮 per-moderator activity stats."
        ),
    },
    {
        "label": "For Admins",
        "emoji": "⚙️",
        "title": "Server Configuration",
        "description": (
            "**/config** (Administrator only) — set the confession channel, "
            "moderator role, approval on/off, logging channel, embed theme, "
            "and sensitive-content alerts.\n\n"
            "The panel updates live as you change settings — no need to rerun "
            "the command to see the new values."
        ),
    },
    {
        "label": "Feedback",
        "emoji": "📮",
        "title": "Feedback",
        "description": (
            "Found a bug, or have an idea for this bot? Use the link below to "
            "share it — every bit of feedback helps."
        ),
        "is_feedback": True,
    },
]

# The feedback page only makes sense to show if a form URL is actually
# configured — otherwise drop it from the guide entirely.
if not FEEDBACK_FORM_URL:
    HELP_SECTIONS = [section for section in HELP_SECTIONS if not section.get("is_feedback")]


async def _resolve_color(interaction: discord.Interaction) -> discord.Color:
    if interaction.guild is None:
        return theme_color(None)
    session = get_session()
    try:
        server = await ServerRepository(session).get(interaction.guild.id)
        return theme_color(server.theme if server else None)
    finally:
        await session.close()


class HelpView(discord.ui.View):
    def __init__(self, color: discord.Color):
        super().__init__(timeout=180)
        self.color = color
        self.page = 0
        self.feedback_button: discord.ui.Button | None = None
        self._update_buttons()

    def build_embed(self) -> discord.Embed:
        section = HELP_SECTIONS[self.page]
        embed = discord.Embed(
            title=f"{section['emoji']} {section['title']}",
            description=section["description"],
            color=self.color,
        )
        embed.set_footer(text=f"Page {self.page + 1}/{len(HELP_SECTIONS)}")
        return embed

    def _update_buttons(self) -> None:
        self.previous_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= len(HELP_SECTIONS) - 1

        if self.feedback_button is not None:
            self.remove_item(self.feedback_button)
            self.feedback_button = None

        if HELP_SECTIONS[self.page].get("is_feedback") and FEEDBACK_FORM_URL:
            self.feedback_button = discord.ui.Button(
                label="Open Feedback Form",
                style=discord.ButtonStyle.link,
                url=FEEDBACK_FORM_URL,
                row=2,
            )
            self.add_item(self.feedback_button)

    @discord.ui.select(
        placeholder="Jump to a section...",
        options=[
            discord.SelectOption(label=section["label"], emoji=section["emoji"], value=str(index))
            for index, section in enumerate(HELP_SECTIONS)
        ],
        row=0,
    )
    async def jump_select(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:
        self.page = int(select.values[0])
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, row=1)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = min(len(HELP_SECTIONS) - 1, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Browse a guide to everything this bot can do.")
    async def help(self, interaction: discord.Interaction) -> None:
        color = await _resolve_color(interaction)
        view = HelpView(color)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))