# Anonymous Confession Bot

A Discord bot for anonymous confessions with moderation tools, user restrictions, and customizable themes.

## Features

- **Anonymous Confessions**: Users can submit confessions anonymously via slash command or interactive buttons
- **Moderator Approval System**: Optional review queue with approve/reject buttons
- **Reply Threads**: Users can reply to existing confessions, creating conversation threads
- **User Restrictions**: Moderators can temporarily or permanently restrict users from submitting confessions
- **Moderator Dashboard**: View statistics and manage the confession queue
- **Logging System**: Comprehensive audit logs for all moderation actions
- **Customizable Themes**: Multiple color themes for embeds
- **Persistent Database**: PostgreSQL-backed storage for all confessions and settings

## Setup

### Prerequisites

- Python 3.8+
- PostgreSQL database
- Discord Bot Token

### Installation

1. **Clone and navigate to the project:**
   ```bash
   cd /workspace
   ```

2. **Create a PostgreSQL database:**
   ```bash
   createdb confession_bot
   ```

3. **Copy the environment example and configure:**
   ```bash
   cp .env.example .env
   ```

4. **Edit `.env` with your credentials:**
   ```env
   DISCORD_TOKEN=your_discord_bot_token
   DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/confession_bot
   ```

5. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

6. **Start the bot:**
   ```bash
   python -m bot.main
   ```

## Discord Configuration

After the bot is running, configure it in your Discord server:

1. **Run `/config`** as an administrator to open the configuration panel
2. **Configure the following:**
   - **Confession Channel** — where approved confessions are published
   - **Moderator Role** — role allowed to approve, reject, and manage submissions
   - **Logging Channel** — private staff channel for audit logs (also serves as review queue when approval is enabled)
   - **Approval Setting** — enable/disable moderator review before posting
   - **Logging Setting** — enable/disable audit logging
   - **Theme** — choose a color theme for embeds

### Required Permissions

The bot needs the following permissions in configured channels:
- View Channel
- Send Messages
- Embed Links
- Read Message History

**Important:** The logging/review channel must be hidden from ordinary members since it displays submitter identities to moderators.

## Commands

### User Commands

| Command | Description |
|---------|-------------|
| `/confess message:<text>` | Submit an anonymous confession (up to 2000 characters) |
| `/confession-status confession_id:<id>` | Check the status of your submission |
| `/status` | Check if the bot is online and view latency |

### Moderator Commands

| Command | Description |
|---------|-------------|
| `/moderator-dashboard` | View confession statistics and quick action buttons |
| `/confession-queue` | List all confessions awaiting review |
| `/confession-delete confession_id:<id> reason:<text>` | Delete a posted confession |
| `/restrict-user user:<@user> duration:<time> reason:<text>` | Restrict a user from submitting confessions |
| `/unrestrict-user user:<@user>` | Lift a user's restriction |
| `/restrictions` | List all currently restricted users |

### Administrator Commands

| Command | Description |
|---------|-------------|
| `/config` | Open the server configuration panel |

## Moderation Workflow

### With Approval Enabled

1. User submits a confession via `/confess` or the "Submit a Confession" button
2. Confession appears in the private logging/review channel with **Approve** and **Reject** buttons
3. Moderators review and decide:
   - **Approve**: Posts anonymously to the confession channel
   - **Reject**: Optionally provide a reason visible only to the submitter
4. All actions are logged in the logging channel

### With Approval Disabled

- Confessions are immediately posted anonymously to the confession channel
- All submissions are still logged for moderation records

## Reply System

- Users can click "💬 Reply" on any public confession to respond
- Replies are threaded under the original confession
- Replies are assigned sequential numbers (e.g., "Anonymous Reply #1")
- Replies go through the same approval process if enabled

## User Restrictions

Moderators can restrict users from submitting confessions:

- **Temporary restrictions**: Specify duration (e.g., `10m`, `2h`, `3d`, `1w`)
- **Permanent restrictions**: Leave duration empty
- **Reason tracking**: Optional reason stored and displayed to the user
- **Audit logging**: All restrictions and lifts are logged

## Database Schema

The bot uses PostgreSQL with the following main tables:

- `servers` — Server configurations and settings
- `confessions` — All confession submissions and their metadata
- `confession_logs` — Audit trail for each confession
- `restrictions` — User restriction records

## Project Structure

```
bot/
├── __init__.py
├── main.py              # Bot entry point and setup
├── cogs/
│   ├── confession.py    # Confession submission and review
│   ├── config.py        # Server configuration commands
│   ├── moderation.py    # Moderator tools and dashboard
│   └── logs.py          # Logging service
├── database/
│   ├── connection.py    # Database connection management
│   ├── models.py        # SQLAlchemy ORM models
│   └── repository.py    # Data access layer
├── errors/
│   └── handlers.py      # Error handling utilities
├── services/
│   └── logging_service.py  # Audit logging functions
└── utils/
    ├── embeds.py        # Embed builders and themes
    ├── helpers.py       # Utility functions
    └── permissions.py   # Permission checking
```

## Troubleshooting

- **Confessions not posting**: Check that the confession channel exists and bot has required permissions
- **Review messages not appearing**: Ensure logging channel is configured and accessible
- **Database connection errors**: Verify `DATABASE_URL` in `.env` and PostgreSQL is running
- **Commands not showing**: Wait a few minutes for Discord to sync slash commands, or restart the bot

## Support

For issues or feature requests, please check the bot's logs for error details. The logging system provides comprehensive information about all operations.
