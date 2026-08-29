import discord


def public_confession_embed(confession_id: int, content: str) -> discord.Embed:
    embed = discord.Embed(title=f"Anonymous Confession #{confession_id}", description=content, color=discord.Color.blurple())
    embed.set_footer(text="Posted anonymously")
    return embed


def moderation_confession_embed(confession_id: int, content: str, author: discord.abc.User) -> discord.Embed:
    embed = discord.Embed(title=f"Confession #{confession_id} awaiting review", description=content, color=discord.Color.gold())
    embed.add_field(name="Submitter (moderators only)", value=f"{author.mention}\n`{author.id}`", inline=False)
    embed.set_footer(text="Approve to post anonymously, or reject with an optional reason.")
    return embed