# Inbox Note BOT

Inbox Note BOT is a Telegram capture bot for a git-backed notes repository.

It accepts text notes, photo captions/images, and uploaded files from one authorized Telegram user, stores them in the target repository's `Inbox/` folder, then commits and pushes the changes over SSH.

## Usage

1. Copy `default.env` to `.env`.
2. Fill in the Telegram token, authorized `TELEGRAM_ID`, SSH helper path, git user details, and target repository path.
3. Run `python bot.py`.

On startup the bot validates the required configuration, clones or updates the target repository at `REPO_PATH`, creates `Inbox/` when needed, and syncs each saved item with git.

Run `python -m pytest` to execute the automated tests.
