#!/usr/bin/env python3
"""
Discord message delete utility (moved to discord_tools/)

This file was moved from the project root into its own folder. See README.md
next to this file for usage and token placement instructions.
"""
import os
import sys
import sysconfig
import logging
import importlib
import importlib.util
from dotenv import load_dotenv


def _ensure_installed_discord_package():
    """Ensure we import the installed `discord` package (discord.py) even if a local
    `discord/` package exists in the project that would shadow it.
    """
    try:
        import discord as _d
        mod_file = getattr(_d, '__file__', '')
        proj_root = os.path.abspath(os.path.dirname(__file__))
        if mod_file and not os.path.abspath(mod_file).startswith(proj_root):
            return
    except Exception:
        pass

    proj_root = os.path.abspath(os.path.dirname(__file__))
    candidate = None
    for p in sys.path:
        if not p:
            continue
        p_abs = os.path.abspath(p)
        if p_abs == proj_root:
            continue
        discord_init = os.path.join(p_abs, 'discord', '__init__.py')
        if os.path.isfile(discord_init):
            candidate = discord_init
            break

    if not candidate:
        purelib = sysconfig.get_paths().get('purelib')
        if purelib:
            discord_init = os.path.join(purelib, 'discord', '__init__.py')
            if os.path.isfile(discord_init):
                candidate = discord_init

    if not candidate:
        return

    spec = importlib.util.spec_from_file_location('discord', candidate)
    module = importlib.util.module_from_spec(spec)
    sys.modules['discord'] = module
    try:
        spec.loader.exec_module(module)  # type: ignore
    except Exception:
        sys.modules.pop('discord', None)
        raise


_ensure_installed_discord_package()


def _import_installed_discord():
    import os, sys, importlib.util

    proj_root = os.path.abspath(os.path.dirname(__file__))
    removed = []
    try:
        for i, p in enumerate(list(sys.path)):
            if not p:
                continue
            p_abs = os.path.abspath(p)
            if p_abs == proj_root:
                removed.append((i, p))
                sys.path.remove(p)

        try:
            import importlib as _il
            module = _il.import_module('discord')
        except Exception:
            module = None

        try:
            import importlib as _il
            commands_module = _il.import_module('discord.ext.commands')
        except Exception:
            commands_module = None

        return (module, commands_module)
    finally:
        for idx, val in removed:
            if val not in sys.path:
                sys.path.insert(idx, val)


disc_tuple = _import_installed_discord()
if isinstance(disc_tuple, tuple):
    discord_lib, commands_module = disc_tuple
else:
    discord_lib = disc_tuple
    commands_module = None

if commands_module is None:
    try:
        commands_module = importlib.import_module('discord.ext.commands')
    except Exception:
        commands_module = None

if discord_lib is None:
    import discord as discord_lib

if commands_module is None:
    commands_module = getattr(discord_lib, 'ext', None)
    if commands_module is not None and hasattr(commands_module, 'commands'):
        commands = commands_module.commands
    else:
        raise ImportError('Could not import discord.ext.commands (local project discord package may be shadowing the installed library)')
else:
    if hasattr(commands_module, 'Bot') or hasattr(commands_module, 'Cog'):
        commands = commands_module
    else:
        commands = getattr(commands_module, 'commands', commands_module)

discord = discord_lib

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Set up bot intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user} (id: {bot.user.id})')


def resolve_channel(guild, channel_key: str):
    if not channel_key:
        return None

    key = channel_key.strip()
    possible_names = []
    if key in ("paper-stop-hunter", "live-stop-hunter"):
        possible_names.append(key)
    else:
        possible_names.append(key)

    for name in possible_names:
        ch = discord.utils.get(guild.text_channels, name=name)
        if ch:
            return ch

    return None


@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int, channel_key: str = None):
    logger.info(f"Received clear command from {ctx.author} amount={amount} channel_key={channel_key}")

    channel = None
    if channel_key:
        channel = resolve_channel(ctx.guild, channel_key)

    if channel is None:
        channel = ctx.channel

    try:
        deleted = await channel.purge(limit=amount)
        msg = await ctx.send(f'Deleted {len(deleted)} messages from {channel.name}.', delete_after=5)
        logger.info(f'Deleted {len(deleted)} messages from {channel.name} (requested by {ctx.author})')
    except discord.Forbidden:
        logger.exception("Missing permissions to delete messages in the target channel")
        await ctx.send("I don't have permission to delete messages in that channel.", delete_after=10)
    except Exception as e:
        logger.exception(f"Failed to purge messages: {e}")
        await ctx.send(f"Failed to delete messages: {e}", delete_after=10)


@clear.error
async def clear_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to manage messages.", delete_after=5)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Invalid arguments. Usage: !clear <amount> [channel_key_or_name]", delete_after=10)
    else:
        logger.exception(f"Unhandled error in clear command: {error}")
        await ctx.send(f"Error: {error}", delete_after=10)


def main():
    IN_FILE_TOKEN = 'REPLACE_ME_WITH_YOUR_BOT_TOKEN'

    token = None
    secret_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '.secret_token')
    try:
        if os.path.isfile(secret_path):
            with open(secret_path, 'r') as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith('#'):
                        continue
                    token = line
                    break
    except Exception:
        pass

    if not token:
        token = IN_FILE_TOKEN if IN_FILE_TOKEN and IN_FILE_TOKEN != 'REPLACE_ME_WITH_YOUR_BOT_TOKEN' else (os.getenv('DISCORD_BOT_TOKEN') or os.getenv('discord_key'))

    if isinstance(token, str):
        token = token.strip()
        token = token.replace('\n', '').replace('\r', '')

    if not token:
        logger.error('No Discord bot token found. Please set .secret_token in this folder, IN_FILE_TOKEN in this file, or DISCORD_BOT_TOKEN/discord_key in the environment.')
        return

    bot.run(token)


def _find_channel_by_name_or_key(guild, name_or_key: str):
    """Helper used by CLI to resolve channel in a guild."""
    # Check project keys
    if name_or_key in ("paper-stop-hunter", "live-stop-hunter"):
        return discord.utils.get(guild.text_channels, name=name_or_key)
    # otherwise try exact name
    return discord.utils.get(guild.text_channels, name=name_or_key)


async def _cli_purge(token: str, guild_id: int, channel_name_or_key: str, amount: int, dry_run: bool):
    # Import here to avoid top-level changes; use the discord imported earlier
    from discord import Intents
    intents = Intents.default()
    intents.messages = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        logger.info(f"CLI connected as {client.user}")
        try:
            guild = client.get_guild(guild_id) or await client.fetch_guild(guild_id)
        except Exception:
            logger.error(f"Guild {guild_id} not found or inaccessible")
            await client.close()
            return

        channel = _find_channel_by_name_or_key(guild, channel_name_or_key)
        if channel is None:
            # Try searching by ID
            try:
                ch_id = int(channel_name_or_key)
                channel = guild.get_channel(ch_id) or await client.fetch_channel(ch_id)
            except Exception:
                channel = None

        if channel is None:
            logger.error(f"Channel '{channel_name_or_key}' not found in guild {guild_id}")
            await client.close()
            return

        logger.info(f"Resolved channel: {channel.name} ({channel.id})")

        # Dry-run: print what would be deleted
        if dry_run:
            logger.info(f"Dry-run: would delete {amount} messages from {channel.name} in guild {guild.name}")
            await client.close()
            return

        # Perform purge
        try:
            deleted = await channel.purge(limit=amount)
            logger.info(f"Deleted {len(deleted)} messages from {channel.name}")
        except discord.Forbidden:
            logger.exception("Missing permissions to purge messages")
        except Exception as e:
            logger.exception(f"Error during purge: {e}")

        await client.close()


def run_cli_mode(args):
    import argparse

    parser = argparse.ArgumentParser(description='CLI purge for discord_tools')
    parser.add_argument('--guild-id', type=int, required=True, help='Guild (server) ID containing the target channel')
    parser.add_argument('--channel', required=True, help='Channel name, project key, or channel ID')
    parser.add_argument('--amount', type=int, required=True, help='Number of messages to delete')
    parser.add_argument('--confirm', action='store_true', help='Actually perform the deletion (otherwise dry-run)')
    parsed = parser.parse_args(args)

    # Load token same way as main
    IN_FILE_TOKEN = 'REPLACE_ME_WITH_YOUR_BOT_TOKEN'
    token = None
    secret_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '.secret_token')
    try:
        if os.path.isfile(secret_path):
            with open(secret_path, 'r') as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith('#'):
                        continue
                    token = line
                    break
    except Exception:
        pass

    if not token:
        token = IN_FILE_TOKEN if IN_FILE_TOKEN and IN_FILE_TOKEN != 'REPLACE_ME_WITH_YOUR_BOT_TOKEN' else (os.getenv('DISCORD_BOT_TOKEN') or os.getenv('discord_key'))

    if isinstance(token, str):
        token = token.strip()
        token = token.replace('\n', '').replace('\r', '')

    if not token:
        logger.error('No token available for CLI mode')
        return

    # If confirm not provided, run dry-run
    dry_run = not parsed.confirm

    import asyncio
    asyncio.run(_cli_purge(token, parsed.guild_id, parsed.channel, parsed.amount, dry_run))


if __name__ == '__main__':
    # If invoked with CLI args, use CLI purge mode
    if len(sys.argv) > 1 and sys.argv[1] != '':
        # Detect if user wants the bot-run interactive mode or CLI mode
        # If user passed known CLI flags, run CLI mode. Simple heuristic: presence of '--guild-id' or '--channel'
        if '--guild-id' in sys.argv or '--channel' in sys.argv:
            run_cli_mode(sys.argv[1:])
        else:
            main()
    else:
        main()


if __name__ == '__main__':
    main()
