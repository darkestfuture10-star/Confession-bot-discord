import discord


class FieldPaginatorView(discord.ui.View):
    """Pages through a list of (name, value) embed fields, 10 per page by
    default. Reused anywhere a list could plausibly exceed Discord's 25
    embed-field limit (restricted users, moderator stats, the review queue)."""

    def __init__(self, title: str, color: discord.Color, fields: list[tuple[str, str]], per_page: int = 10, empty_message: str = "Nothing to show."):
        super().__init__(timeout=180)
        self.title = title
        self.color = color
        self.fields = fields
        self.per_page = per_page
        self.empty_message = empty_message
        self.page = 0
        self.max_page = max(0, (len(fields) - 1) // per_page) if fields else 0
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.previous_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= self.max_page

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.title, color=self.color)
        if not self.fields:
            embed.description = self.empty_message
            return embed
        start = self.page * self.per_page
        for name, value in self.fields[start:start + self.per_page]:
            embed.add_field(name=name, value=value, inline=False)
        if self.max_page > 0:
            embed.set_footer(text=f"Page {self.page + 1}/{self.max_page + 1} • {len(self.fields)} total")
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = min(self.max_page, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)