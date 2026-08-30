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
