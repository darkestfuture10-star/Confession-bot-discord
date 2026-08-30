import discord


def public_confession_embed(confession_id: int, content: str, parent_id: int | None = None) -> discord.Embed:
    embed = discord.Embed(title=f"Anonymous Confession #{confession_id}", description=content, color=discord.Color.blurple())
    footer = "Posted anonymously"
    if parent_id:
        footer = f"↩️ Reply to Confession #{parent_id} • {footer}"
    embed.set_footer(text=footer)
    return embed


def moderation_confession_embed(confession_id: int, content: str, author: discord.abc.User, parent_id: int | None = None) -> discord.Embed:
    embed = discord.Embed(title=f"Confession #{confession_id} awaiting review", description=content, color=discord.Color.gold())
    if parent_id:
        embed.add_field(name="Replying to", value=f"Confession #{parent_id}", inline=False)
    embed.add_field(name="Submitter (moderators only)", value=f"{author.mention}\n`{author.id}`", inline=False)
    embed.set_footer(text="Approve to post anonymously, or reject with an optional reason.")
    return embed
