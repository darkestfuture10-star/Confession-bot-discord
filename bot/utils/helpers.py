import re
from datetime import timedelta


def extract_confession_id(title: str | None, prefix: str) -> int | None:
    """Pull the numeric confession ID out of an embed title like
    'Confession #5 awaiting review' or 'Anonymous Confession #5'.
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
    the footer as 'Confession ID: N'."""
    if not footer_text:
        return None
    match = re.search(r"Confession ID:\s*(\d+)", footer_text)
    return int(match.group(1)) if match else None


_DURATION_UNITS = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def parse_duration(value: str) -> timedelta:
    """Parse a short duration string like '10m', '2h', '3d', or '1w'."""
    match = re.fullmatch(r"\s*(\d+)\s*([mhdw])\s*", value.lower())
    if not match:
        raise ValueError("Duration must look like 10m, 2h, 3d, or 1w.")
    amount, unit = match.groups()
    return timedelta(**{_DURATION_UNITS[unit]: int(amount)})


def normalize_for_comparison(content: str) -> str:
    """Collapse whitespace/case so near-identical duplicate submissions match."""
    return " ".join(content.strip().lower().split())


def looks_like_spam(content: str) -> bool:
    """Cheap content-pattern heuristics, not frequency-based. Catches the
    obvious junk (near-empty, repeated-character, mostly-symbol) without
    needing any external model."""
    stripped = content.strip()
    if len(stripped) < 3:
        return True

    if len(stripped) >= 10:
        alnum_count = sum(1 for character in stripped if character.isalnum())
        if alnum_count / len(stripped) < 0.3:
            return True

        unique_characters = set(stripped.lower().replace(" ", ""))
        if len(unique_characters) <= 2:
            return True

    return False


# Non-exhaustive starting list — expand as needed. Matching is intentionally
# simple substring matching: this is a heads-up flag for moderators to review
# more carefully, never a block or an automated response to the submitter.
_SENSITIVE_KEYWORDS = (
    "kill myself",
    "want to die",
    "end my life",
    "ending my life",
    "suicide",
    "suicidal",
    "self harm",
    "self-harm",
    "hurting myself",
    "cutting myself",
    "no reason to live",
    "overdose",
)


def contains_sensitive_keywords(content: str) -> bool:
    lowered = content.lower()
    return any(keyword in lowered for keyword in _SENSITIVE_KEYWORDS)