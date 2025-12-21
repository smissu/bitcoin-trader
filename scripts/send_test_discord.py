#!/usr/bin/env python3
"""
Simple test script to send a Discord message to the `bitcoin-trader` webhook
Uses the existing `discord/messages.py` send_msg function.

Usage:
  # activate the conda env first
  conda activate bitcoin-trader
  python scripts/send_test_discord.py --message "Hello from test"

Options:
  --message, -m   Message text to send (default: test string)
  --yes, -y       Skip confirmation prompt
"""

import argparse
from dotenv import load_dotenv
import os

# Ensure environment variables are loaded (discord/messages.py also does this,
# but loading here makes behavior explicit when running the script directly)
load_dotenv()

# Import the project's messaging helper
# Load the local `discord/messages.py` file directly to avoid shadowing by the installed `discord` package
from pathlib import Path
import importlib.util
messages_path = Path(__file__).resolve().parents[1] / "discord" / "messages.py"
spec = importlib.util.spec_from_file_location("discord_messages", messages_path)
messages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(messages)


def main():
    parser = argparse.ArgumentParser(description='Send a test Discord message')
    parser.add_argument('--message', '-m', default='Test message from bitcoin-trader',
                        help='Text message to send')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    print(f"Ready to send to 'bitcoin-trader' channel: \n\t{args.message}\n")

    if not args.yes:
        confirm = input('Send message? [y/N]: ').strip().lower()
        if confirm not in ('y', 'yes'):
            print('Aborted.')
            return

    # Send message (send_msg will log errors if it fails)
    messages.send_msg(args.message, strat='bitcoin-trader', toPrint=True)
    print('Done — check Discord and pionex_downloader.log for details')


if __name__ == '__main__':
    main()
