# Anonymous Confession Bot

## Setup

1. Create a PostgreSQL database and copy `.env.example` to `.env`.
2. Set `DISCORD_TOKEN` and `DATABASE_URL` in `.env`.
3. Install the packages in `requirements.txt` and start `bot/main.py`.
4. In Discord, run `/config` as an administrator. Configure:
   - **Confession Channel** — where approved confessions are published.
   - **Moderator Role** — role allowed to approve and reject submissions.
   - **Logging Channel** — a private staff channel. When approval is enabled, it is also the review queue.

The bot needs View Channel, Send Messages, Embed Links, and Read Message History in the configured channels. The logging/review channel must not be visible to ordinary members, because it displays a submitter's identity to moderators.

## Commands

- `/confess message:<text>` — submit an anonymous confession.
- `/confession-status confession_id:<id>` — view the status of one of your submissions.
- `/config` — configure the bot (administrators only).

With moderator approval enabled, the bot sends each submission to the private review queue with **Approve** and **Reject** buttons. Approval publishes an embed titled `Anonymous Confession #<id>`; it contains no submitter identity. Rejections can include a private reason visible only through the submitter's status command.

With approval disabled, submissions are immediately posted anonymously. Every submission, decision, and posting failure is saved in PostgreSQL. Discord audit messages are additionally sent when logging is enabled.
