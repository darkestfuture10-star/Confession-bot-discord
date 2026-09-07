# 🤫 Confession Bot

A production-ready Discord confession bot built with **Python**,
**discord.py**, **PostgreSQL**, and **SQLAlchemy**.

Confession Bot allows members of a Discord server to submit anonymous
confessions while giving moderators the tools they need to review,
manage, and audit activity.

The bot is designed to keep the public confession experience anonymous
while maintaining the necessary private information for moderation and
server management.

------------------------------------------------------------------------

## ✨ Features

### 📝 Anonymous Confessions

-   Submit confessions through a Discord modal.
-   Confessions are stored in PostgreSQL.
-   Every confession receives a unique ID.
-   Public confessions do not reveal the author's identity.
-   Author information is stored privately for moderation purposes.
-   Supports moderator approval before publication.
-   Supports automatic publication when approval is disabled.

### 💬 Replies

-   Members can reply to confessions.
-   Replies are handled as part of the confession system.
-   Replies use their own reply numbering.
-   Replies remain anonymous publicly.
-   Reply activity can be tracked through the bot's logging system.

### 🛡️ Moderation

-   Moderator approval queue.
-   Approve or reject confessions.
-   Delete published confessions.
-   Restrict users from submitting confessions.
-   Temporary restrictions.
-   Permanent restrictions.
-   Unrestrict users.
-   View active restrictions.
-   Moderator-only tools and permissions.

### 📊 Moderator Dashboard

The bot includes an interactive moderator dashboard for managing the
confession system without requiring a separate command for every action.

Dashboard functionality includes:

-   Pending confession count
-   Approved confession count
-   Rejected confession count
-   Deleted confession count
-   Active restriction count
-   Confession queue
-   Log search
-   User restriction management
-   User unrestriction
-   Restricted-user list
-   Confession deletion
-   Statistics
-   Settings
-   Help

The dashboard uses Discord buttons, selectors, and modals for a cleaner
moderation workflow.

### 📋 Moderation & Audit Logs

Moderation activity can be stored and reviewed through the audit-log
system.

Logs can include:

-   Confession submission
-   Approval
-   Rejection
-   Deletion
-   Publication failures
-   Review-delivery failures
-   Reports
-   Moderator responsible for an action
-   Additional action details
-   Timestamp

Moderators can search the audit trail using a confession ID.

### ⚙️ Server Configuration

Each server can configure its own confession system.

Configuration includes:

-   Confession channel
-   Moderator role
-   Moderator approval
-   Logging
-   Logging channel
-   Theme
-   Configuration reset

### 🎨 Themes

The bot supports multiple built-in themes:

-   Default
-   Nothing Style
-   Monochrome
-   Classic & Minimal

### 👤 User Features

Users can interact with the confession system without needing access to
moderator tools.

Features include:

-   Submit confessions
-   Reply to confessions
-   Check confession status
-   Respect active user restrictions
-   Use the anonymous confession workflow

------------------------------------------------------------------------

# 🏗️ Technology Stack

  Component               Technology
  ----------------------- ------------------------------------------
  Language                Python
  Discord API             discord.py
  Database                PostgreSQL
  ORM                     SQLAlchemy
  Async database driver   asyncpg
  Production database     Neon PostgreSQL
  Configuration           Environment variables
  UI                      Discord Views, Buttons, Selects & Modals

The project uses asynchronous database operations to avoid blocking the
Discord bot while communicating with PostgreSQL.

------------------------------------------------------------------------

# 📁 Project Structure

A typical project structure looks like:

``` text
Confession-bot-discord/
│
├── bot/
│   ├── cogs/
│   │   ├── confession.py
│   │   ├── moderation.py
│   │   ├── logs.py
│   │   └── config.py
│   │
│   ├── database/
│   │   ├── connection.py
│   │   ├── models.py
│   │   └── repository.py
│   │
│   ├── services/
│   │   └── logging_service.py
│   │
│   ├── utils/
│   │   ├── embeds.py
│   │   ├── helpers.py
│   │   └── permissions.py
│   │
│   └── ...
│
├── .env
├── .gitignore
├── requirements.txt
├── README.md
└── ...
```

Your exact structure may contain additional modules depending on the
current version of the project.

------------------------------------------------------------------------

# 🚀 Installation

## 1. Requirements

Before installing the bot, make sure you have:

-   Python 3.11+ recommended
-   A Discord application/bot
-   A PostgreSQL database
-   Git
-   Internet access from the machine running the bot

For production hosting, use a host that supports a continuously running
Python process.

------------------------------------------------------------------------

## 2. Clone the Repository

``` bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd <YOUR_REPOSITORY_DIRECTORY>
```

------------------------------------------------------------------------

## 3. Create a Virtual Environment

### Windows

``` powershell
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

------------------------------------------------------------------------

## 4. Install Dependencies

``` bash
pip install -r requirements.txt
```

If the project does not already contain a `requirements.txt`, install
the project's required packages and then generate one:

``` bash
pip freeze > requirements.txt
```

Do not commit the virtual environment itself.

------------------------------------------------------------------------

# 🔐 Environment Variables

Create a `.env` file in the project root.

Example:

``` env
DISCORD_TOKEN=your_discord_bot_token
DATABASE_URL=postgresql+asyncpg://username:password@host/database?ssl=require
```

Do **not** commit your `.env` file.

Your `.gitignore` should contain at least:

``` gitignore
.env
.venv/
__pycache__/
*.pyc
```

### Important

Never publish:

-   Discord bot tokens
-   Database passwords
-   API keys
-   Private credentials
-   Production secrets

If a token or password is accidentally committed, revoke/rotate it
immediately.

------------------------------------------------------------------------

# 🤖 Creating the Discord Bot

## 1. Create a Discord Application

Open the Discord Developer Portal and create a new application.

Create a bot under the application and copy its token.

Store the token in your `.env` file:

``` env
DISCORD_TOKEN=your_token
```

Never place the token directly inside Python source code.

------------------------------------------------------------------------

## 2. Required Bot Permissions

The exact permissions depend on the features enabled in your server, but
the bot generally needs permissions to:

-   View channels
-   Send messages
-   Embed links
-   Read message history
-   Use application commands
-   Manage messages where moderation features require it

Only grant permissions that the bot actually needs.

------------------------------------------------------------------------

## 3. Invite the Bot

Generate an OAuth2 invite URL from the Discord Developer Portal.

Select:

``` text
Scopes:
☑ bot
☑ applications.commands
```

Then select the permissions required by the bot.

Invite the bot to your test server first.

------------------------------------------------------------------------

# 🗄️ PostgreSQL / Neon Setup

The bot uses PostgreSQL for persistent storage.

For production, the project can use Neon PostgreSQL.

Create a Neon project and obtain its PostgreSQL connection string.

For SQLAlchemy's asynchronous engine, the connection URL should use an
async driver:

``` env
DATABASE_URL=postgresql+asyncpg://username:password@host/database?ssl=require
```

The exact connection parameters depend on the database provider and
connection string supplied by the provider.

### Database Tables

The project currently uses tables for areas such as:

``` text
servers
confessions
user_restrictions
confession_reports
moderation_logs
```

The application's database initialization/migration process should be
used when deploying a fresh database.

For an existing production database, use proper migrations rather than
assuming `create_all()` will modify existing tables.

------------------------------------------------------------------------

# ▶️ Running the Bot

Activate the virtual environment and start the bot using the project's
main entry point.

For example:

``` bash
python main.py
```

If your project uses another entry point, use that file instead.

A successful startup should connect to Discord and initialize the
database without errors.

------------------------------------------------------------------------

# ⚙️ Initial Server Setup

After inviting the bot:

1.  Create a confession channel.
2.  Create/select a moderator role.
3.  Run the configuration command.
4.  Select the confession channel.
5.  Select the moderator role.
6.  Configure approval.
7.  Configure logging.
8.  Select a logging channel if logging is enabled.
9.  Choose a theme.
10. Test the confession workflow.

The exact configuration command and options depend on the current bot
build.

------------------------------------------------------------------------

# 🧪 Recommended Testing

Before deploying the bot publicly, test it in a private Discord server.

### Confession Testing

-   [ ] Submit a confession.
-   [ ] Confirm it is stored.
-   [ ] Confirm the public post is anonymous.
-   [ ] Confirm the author is not exposed publicly.
-   [ ] Test approval mode.
-   [ ] Test automatic publication mode.
-   [ ] Test rejection.
-   [ ] Test deletion.

### Reply Testing

-   [ ] Reply to a confession.
-   [ ] Confirm reply numbering.
-   [ ] Confirm replies remain anonymous.
-   [ ] Test multiple replies.
-   [ ] Test invalid/deleted targets.

### Moderation Testing

-   [ ] Open the moderator dashboard.
-   [ ] Open the queue.
-   [ ] Search confession logs.
-   [ ] Restrict a user.
-   [ ] Test a temporary restriction.
-   [ ] Test a permanent restriction.
-   [ ] Unrestrict the user.
-   [ ] View restricted users.
-   [ ] Delete a confession.

### Permission Testing

Test with:

-   Normal member
-   Moderator
-   Server administrator

Confirm that normal members cannot access moderator-only functionality.

### Failure Testing

Also test:

-   Deleted confession channel
-   Deleted logging channel
-   Missing bot permissions
-   Deleted messages
-   Invalid confession IDs
-   Invalid restriction durations
-   Database connection failure
-   Expired dashboard interactions

------------------------------------------------------------------------

# 🌐 Production Hosting

The bot should run on a host that supports a persistent Python
worker/process.

Common deployment options include:

-   VPS
-   Cloud VM
-   Container-based hosting
-   Python worker hosting
-   Other services that support long-running Discord bots

The bot should **not** be deployed as a short-lived HTTP-only
application unless the hosting provider explicitly supports persistent
background workers.

------------------------------------------------------------------------

# 🖥️ Example Linux Deployment

After connecting to a Linux server:

``` bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd <YOUR_REPOSITORY_DIRECTORY>
```

Create the environment:

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

``` bash
pip install -r requirements.txt
```

Create the environment file:

``` bash
nano .env
```

Add:

``` env
DISCORD_TOKEN=your_token
DATABASE_URL=your_database_url
```

Test the bot:

``` bash
python main.py
```

Once confirmed, configure a process manager such as `systemd` or another
supported process manager so the bot automatically restarts after
crashes or server reboots.

------------------------------------------------------------------------

# 🔄 Updating the Production Bot

When new code is pushed to GitHub:

``` bash
git pull
```

Activate the virtual environment:

``` bash
source .venv/bin/activate
```

Update dependencies if necessary:

``` bash
pip install -r requirements.txt
```

Restart the bot using your process manager.

Do not overwrite the production `.env`.

------------------------------------------------------------------------

# 🔒 Security

Security is especially important because confession systems handle
private user information.

### Anonymous Public Content

The bot should never publicly expose the Discord identity associated
with a confession.

Moderator-only information must remain restricted to authorized staff.

### Database

Protect the production database credentials.

Never commit:

``` text
.env
database passwords
Discord tokens
API keys
private credentials
```

### Discord Permissions

Use the minimum permissions necessary for the bot.

Regular members should not be able to access moderator-only commands,
buttons, modals, or dashboard functionality.

------------------------------------------------------------------------

# 🧩 Architecture

The project separates responsibilities into different layers.

### Cogs

Discord commands and interactive UI live inside cogs.

Examples:

``` text
confession.py
moderation.py
logs.py
config.py
```

### Database

Database models define the PostgreSQL schema:

``` text
models.py
```

Database operations are handled through repositories:

``` text
repository.py
```

### Services

Reusable application services handle functionality such as event
logging.

### Utilities

Shared functionality such as:

-   Permissions
-   Embed styling
-   Duration parsing
-   Helpers

is kept separate from the Discord command implementations.

This structure makes it easier to add features without putting the
entire bot into one file.

------------------------------------------------------------------------

# 🛠️ Development Guidelines

When contributing to the project:

-   Keep functions focused.
-   Avoid unnecessary duplication.
-   Reuse existing repositories and services.
-   Keep database operations asynchronous.
-   Validate user input.
-   Protect moderator-only interactions.
-   Handle Discord API failures gracefully.
-   Avoid hardcoding secrets.
-   Keep comments concise and useful.
-   Clearly mark temporary test code.

Example:

``` python
#temp test
...
#temp test
```

Temporary testing code should be removed before production releases.

------------------------------------------------------------------------

# 🗺️ Development Status

The major core development phases are complete.

  Phase                         Status
  ----------------------------- ----------------------
  Foundation                    ✅ Complete
  Server Configuration          ✅ Complete
  Confession Core               ✅ Complete
  Replies                       ✅ Complete
  Moderation                    ✅ Complete
  Reports                       ⚪ Canceled
  Statistics & Logs             ✅ Complete
  User Features                 ✅ Complete
  Moderator Dashboard / UX      ✅ Complete
  Security & Reliability        ✅ \~99.99%
  Production Deployment         🔄 Final preparation
  Premium / Advanced Features   🔮 Future

The project is currently focused on final production preparation,
hosting, documentation, and release.

------------------------------------------------------------------------

# 📌 Roadmap

Future development may include optional advanced or premium
functionality.

Possible future additions:

-   Advanced analytics
-   Custom server branding
-   Additional themes
-   Advanced moderation automation
-   AI-assisted moderation
-   Server-specific customization
-   Premium server features

Core confession functionality is intended to remain useful without
requiring premium features.

------------------------------------------------------------------------

# 🐛 Troubleshooting

## Bot does not start

Check:

``` text
DISCORD_TOKEN
DATABASE_URL
```

Then verify that dependencies are installed:

``` bash
pip install -r requirements.txt
```

------------------------------------------------------------------------

## `psycopg2` / async driver error

If SQLAlchemy reports that `psycopg2` is being used with an asynchronous
engine, check that the database URL uses the async driver:

``` env
postgresql+asyncpg://...
```

and ensure `asyncpg` is installed:

``` bash
pip install asyncpg
```

------------------------------------------------------------------------

## Database connection fails

Check:

-   Database is running.
-   Connection string is correct.
-   Username/password are correct.
-   SSL settings match your provider.
-   Network access is available.
-   The `.env` file is being loaded.

For Neon, use the connection information supplied by your Neon project.

------------------------------------------------------------------------

## Bot responds but slash commands are missing

Check that:

-   The bot was invited with `applications.commands`.
-   The bot is connected to the correct Discord application.
-   Commands are being synced by the application.
-   Discord has had time to update the command registration.

------------------------------------------------------------------------

## Bot crashes after deployment

Check the hosting provider's logs first.

Look for:

-   Python traceback
-   Database errors
-   Discord permission errors
-   Missing environment variables
-   Import errors
-   Dependency errors

Do not hide exceptions during development. Fix the underlying problem
and keep production logging useful.

------------------------------------------------------------------------

# 🤝 Contributing

Contributions are welcome if this repository is opened for public
contributions.

Before submitting changes:

1.  Create a branch.
2.  Make the change.
3.  Test the affected feature.
4.  Test related moderation/security behavior.
5.  Keep commits focused.
6.  Open a pull request with a clear description.

Please avoid committing secrets, generated environments, or unnecessary
files.

------------------------------------------------------------------------

# 📄 License

This project does not currently specify a license.

If you intend to make the repository open source, add an appropriate
`LICENSE` file before presenting the project as open-source software.

Recommended choices depend on how you want others to use, modify, and
redistribute the bot.

------------------------------------------------------------------------

# ⚠️ Disclaimer

This bot is provided as a software project and should be configured and
tested according to the needs of the server where it is deployed.

Server administrators are responsible for:

-   Moderation policies
-   User privacy
-   Content rules
-   Staff permissions
-   Database access
-   Compliance with applicable laws and Discord's policies

Always test configuration and permissions in a private server before
deploying to a larger community.

------------------------------------------------------------------------

# 🤫 About

**Confession Bot** is built to provide a simple anonymous confession
experience for Discord communities while giving moderators the tools
required to safely manage that content.

The goal is a clean separation between:

``` text
PUBLIC
Anonymous confessions
Anonymous replies
User-facing features

            ↓

PRIVATE
Moderator tools
Author information
Moderation actions
Audit logs
Statistics
```

Built with Python, discord.py, PostgreSQL, and SQLAlchemy.
