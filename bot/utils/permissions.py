import discord


def can_moderate(member: discord.Member, moderator_role_id: int | None) -> bool:
    return member.guild_permissions.administrator or (
        moderator_role_id is not None and any(role.id == moderator_role_id for role in member.roles)
    )