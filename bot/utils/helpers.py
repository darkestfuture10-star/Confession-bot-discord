import re


def extract_confession_id(title: str | None, prefix: str) -> int | None:
    """Pull the numeric confession ID out of an embed title like
    'Confession #5 awaiting review' or 'Anonymous Confession #5'.

    Persistent Discord UI views don't carry per-message state after a bot
    restart, so buttons on confession messages recover which confession they
    belong to by reading the leading digits straight out of the embed title
    rather than relying on a dynamic custom_id.
    """
    if not title or not title.startswith(prefix):
        return None
    remainder = title.removeprefix(prefix).strip()
    digits = ""
    for character in remainder:
        if character.isdigit():
            digits += character
        else:
            break
    return int(digits) if digits else None


def extract_confession_id_from_footer(footer_text: str | None) -> int | None:
    """Public confession/reply embeds always encode the real confession ID in
    the footer as 'Confession ID: N', independent of whatever number is shown
    in the title (the per-type Confession/Reply counter)."""
    if not footer_text:
        return None
    match = re.search(r"Confession ID:\s*(\d+)", footer_text)
    return int(match.group(1)) if match else None