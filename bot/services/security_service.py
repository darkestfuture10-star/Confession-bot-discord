from datetime import datetime, timedelta

import discord

from bot.database.models import Server
from bot.database.repository import ConfessionRepository
from bot.services.logging_service import send_event_log
from bot.utils.helpers import looks_like_spam, normalize_for_comparison

# --- Relaxed defaults, tuned for a small/casual server. Adjust freely. ---
COOLDOWN_SECONDS = 15
RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW_SECONDS = 60 * 60  # 1 hour
MAX_PENDING_QUEUE = 30
BURST_THRESHOLD = 8
BURST_WINDOW_SECONDS = 60
BURST_ALERT_COOLDOWN_SECONDS = 5 * 60


# In-memory, one-shot waivers a moderator can grant so a specific user's
# very next submission skips the cooldown/rate-limit checks. Resets on
# restart, which is fine — a mod can just re-grant it if that ever matters.
_cooldown_waivers: set[tuple[int, int]] = set()


def waive_next_submission(server_id: int, user_id: int) -> None:
    _cooldown_waivers.add((server_id, user_id))


def _consume_waiver(server_id: int, user_id: int) -> bool:
    key = (server_id, user_id)
    if key in _cooldown_waivers:
        _cooldown_waivers.discard(key)
        return True
    return False


async def evaluate_submission(confessions: ConfessionRepository, server: Server, author_id: int, content: str) -> str | None:
    """Runs the 8.1/8.2/8.3/8.7 checks. Returns an error message if the
    submission should be blocked, or None if it's allowed. Mention
    sanitization (8.4) is handled separately by the caller via
    ``discord.utils.escape_mentions``, since it doesn't block anything."""

    if looks_like_spam(content):
        return "❌ That doesn't look like a real confession (too short, repeated characters, or mostly symbols)."

    now = datetime.utcnow()
    waived = _consume_waiver(server.id, author_id)

    if not waived:
        last_time = await confessions.get_last_submission_time(server.id, author_id)
        if last_time is not None:
            elapsed = (now - last_time).total_seconds()
            if elapsed < COOLDOWN_SECONDS:
                wait = int(COOLDOWN_SECONDS - elapsed) + 1
                return f"⏳ Please wait {wait}s before submitting another confession."

        recent_count = await confessions.count_recent_by_author(
            server.id, author_id, now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
        )
        if recent_count >= RATE_LIMIT_MAX:
            return f"❌ You've hit the limit of {RATE_LIMIT_MAX} confessions per hour. Please try again later."

    last_content = await confessions.get_last_content_by_author(server.id, author_id)
    if last_content is not None and normalize_for_comparison(last_content) == normalize_for_comparison(content):
        return "❌ You already submitted that exact confession."

    if server.approval_enabled:
        pending_count = await confessions.count_pending(server.id)
        if pending_count >= MAX_PENDING_QUEUE:
            return "❌ The review queue is currently full. Please try again once moderators catch up."

    return None


# Per-server rolling timestamps for burst detection. In-memory only —
# resets on restart, which is fine for a short-window spam signal.
_recent_submissions: dict[int, list[datetime]] = {}
_last_burst_alert: dict[int, datetime] = {}


async def record_and_check_burst(guild: discord.Guild, server: Server) -> None:
    """8.5 mass-confession protection: alerts moderators if a burst of
    confessions lands server-wide in a short window. Does not block or
    auto-lock anything — mods decide what to do via the moderation panel."""
    now = datetime.utcnow()
    timestamps = _recent_submissions.setdefault(server.id, [])
    timestamps.append(now)

    cutoff = now - timedelta(seconds=BURST_WINDOW_SECONDS)
    while timestamps and timestamps[0] < cutoff:
        timestamps.pop(0)

    if len(timestamps) < BURST_THRESHOLD:
        return

    last_alert = _last_burst_alert.get(server.id)
    if last_alert is not None and (now - last_alert).total_seconds() < BURST_ALERT_COOLDOWN_SECONDS:
        return

    _last_burst_alert[server.id] = now
    await send_event_log(
        guild, server, "🚨 Possible Confession Spam Detected",
        description=(
            f"{len(timestamps)} confessions were submitted in the last {BURST_WINDOW_SECONDS} seconds. "
            "Check the moderation panel's queue, or consider disabling `/confess` temporarily if this looks like a raid."
        ),
    )
