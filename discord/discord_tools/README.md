# Discord Tools — delete_discord_msgs

This folder contains the Discord message deletion utility moved from the project root.

Usage

1. Install dependencies in your project environment (see project `requirements.txt`).

2. Provide your bot token by one of these methods (priority order):
   - Create `discord_tools/.secret_token` with the bot token on a single line (no quotes).
   - Edit `IN_FILE_TOKEN` in `discord_tools/delete_discord_msgs.py` (file is gitignored).
   - Set environment variable `DISCORD_BOT_TOKEN` or `discord_key`.

3. Run the bot with the project Python interpreter:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/future_trader/bin/python ./discord_tools/delete_discord_msgs.py
```

Commands

- `!clear <amount> [channel_key_or_name]` — delete recent messages.
  - `channel_key_or_name` supports project keys: `paper-stop-hunter`, `live-stop-hunter`, or an exact channel name.
  - The user issuing the command must have Manage Messages permission.

Notes

- The bot requires the Message Content Intent to be enabled in the Discord Developer Portal.
- The bot must be invited to the server and have Manage Messages permission in the target channel.
- The folder and its `.secret_token` are added to `.gitignore` to prevent accidental commits.

## Recommended secret handling

Prefer environment variables for secrets. Examples:

1. Create a `.env` file in the project root and add:

```
DISCORD_KEY=Bearer <your-token>
```

2. Or, to keep a local token file, copy `.secret_token.example` to `discord_tools/.secret_token` and add your token there. That file is ignored by git.

`discord/messages.py` will read `DISCORD_KEY` from the environment using `python-dotenv` (recommended).
