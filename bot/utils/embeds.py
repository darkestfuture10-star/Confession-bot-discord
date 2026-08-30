import discord


THEMES: dict[str, dict[str, str]] = {
    "default": {"label": "Default", "emoji": "🔵", "color": "#5865F2"},
    "monochrome": {"label": "Monochrome", "emoji": "⬛", "color": "#99AAB5"},
    "cyberpunk": {"label": "Cyberpunk", "emoji": "🌆", "color": "#F72585"},
    "white": {"label": "Fully White", "emoji": "⬜", "color": "#FFFFFF"},
    "midnight": {"label": "Midnight Blue", "emoji": "🌌", "color": "#191970"},
}

DEFAULT_THEME = "default"


def theme_color(theme: str | None) -> discord.Color:
    data = THEMES.get(theme or DEFAULT_THEME, THEMES[DEFAULT_THEME])
    return discord.Color(int(data["color"].lstrip("#"), 16))


def theme_label(theme: str | None) -> str:
    return THEMES.get(theme or DEFAULT_THEME, THEMES[DEFAULT_THEME])["label"]


def public_confession_embed(confession_id: int, content: str, parent_id: int | None = None, reply_number: int | None = None, theme: str | None = None) -> discord.Embed:
    title = f"Anonymous Reply #{reply_number}" if reply_number is not None else f"Anonymous Confession #{confession_id}"
    embed = discord.Embed(title=title, description=content, color=theme_color(theme))
    footer = f"Posted anonymously • Confession ID: {confession_id}"
    if parent_id:
        footer = f"↩️ Reply to Confession #{parent_id} • {footer}"
    embed.set_footer(text=footer)
    return embed


def moderation_confession_embed(confession_id: int, content: str, author: discord.abc.User, parent_id: int | None = None, reply_number: int | None = None, theme: str | None = None) -> discord.Embed:
    embed = discord.Embed(title=f"Confession #{confession_id} awaiting review", description=content, color=theme_color(theme))
    if parent_id:
        embed.add_field(name="Replying to", value=f"Confession #{parent_id}", inline=False)
    if reply_number is not None:
        embed.add_field(name="Will post as", value=f"Anonymous Reply #{reply_number}", inline=False)
    embed.add_field(name="Submitter (moderators only)", value=f"{author.mention}\n`{author.id}`", inline=False)
    embed.set_footer(text="Approve to post anonymously, or reject with an optional reason.")
    return embed