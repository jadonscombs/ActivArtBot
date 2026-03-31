"""
Discord bot application for auto-assigning roles and guild management.
"""
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging
from pathlib import Path

from utils_dir.constants import (
    logger,
    COGS_DIR_PATH,
    PY_EXTENSION,
    BOT_TOKEN_KEY,
    NULL_STR
)

# Load environment variables
load_dotenv()


def load_extensions(bot: discord.Bot, cogs_dir: Path = COGS_DIR_PATH) -> None:
    logger.debug(f"Loading extensions from '{cogs_dir}'")

    # Populate list of cogs to load
    cog_list: list = []
    for filename in os.listdir(cogs_dir):
        filename_path: Path = Path(filename)
        if (
            not filename_path.suffix == PY_EXTENSION
            or filename.endswith("__init__.py")
        ):
            continue

        logger.info(f"Cog found: '{filename}'")
        cog_list.append(
            f"{cogs_dir.name}.{filename_path.stem}"
        )
    logger.info(f"Cogs discovered: {len(cog_list)}")

    # Attempt to load each cog into the Discord Bot
    for cog in cog_list:
        try:
            logger.info(f"Attempting to load cog {cog}")
            bot.load_extension(cog)
        except Exception:
            logger.exception("Exception: ")

    logger.info(f"Cogs loaded: {len(bot.extensions)}")


def is_bot_author(message: discord.Message, bot: discord.Bot) -> bool:
    return message.author == bot.user


def create_bot() -> discord.Bot:

    # Initialize discord meta parameters
    intents = discord.Intents.all()
    intents.message_content = True
    bot: discord.Bot = discord.Bot(intents=intents)

    # Create event listeners
    @bot.event
    async def on_ready():
        logger.info(
            f'Initialized. Logged in as {bot.user} ({int(1000*bot.latency)}ms)'
        )

    @bot.event
    async def on_message(message: discord.Message):
        if is_bot_author(message, bot):
            return

    # Create slash commands
    @bot.slash_command(
        name='ping',
        description='Connectivity check - displays bot latency'
    )
    async def ping(ctx):
        await ctx.respond(f"latency: {int(1000*bot.latency)}ms")

    # Return bot instance
    return bot


def main():
    """Main entry point for the bot."""
    bot = create_bot()
    load_extensions(bot)

    # Start the bot
    try:
        logger.info("Starting bot...")
        bot.run(os.getenv(BOT_TOKEN_KEY, NULL_STR))
    except discord.LoginFailure:
        logger.error("Invalid Discord token. Please check your .env file.")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Exception: ")
