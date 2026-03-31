"""
Constants and utility functions for the Discord bot.
"""

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Any, Optional

# Basic constants
NULL_STR = ""
NONE_STR = "None"
PY_EXTENSION = ".py"
BOT_TOKEN_KEY = "BOT_TOKEN"

# File paths
CONFIG_FILE = Path("config.json")
LOG_DIR = Path("logs")
COGS_DIR_NAME = "cogs_dir"
COGS_DIR_PATH = Path(COGS_DIR_NAME)

# Auto role constants
AUTOROLE_TRIGGER_KEY = "auto-role-trigger"
AUTOROLE_INSTANT_MODE = "instant"
AUTOROLE_MESSAGE_MODE = "intro-message"
AUTOROLE_DELAY_SEC_KEY = "auto-role-delay-sec"
AUTOROLE_DELAY_SEC = 300
INTRO_CHANNEL_ID_KEY = "intro-channel-id"
ADMIN_ROLE_IDS_KEY = "admin-role-ids"
VERIFIED_ROLE_IDS_KEY = "verified-role-ids"
ADMIN_CHANNEL_ID_KEY = "admin-channel-id"

# Default values
DEFAULT_GUILD_CONFIG = {
    VERIFIED_ROLE_IDS_KEY: [],
    ADMIN_CHANNEL_ID_KEY: -1,
    ADMIN_ROLE_IDS_KEY: [],
    AUTOROLE_TRIGGER_KEY: AUTOROLE_INSTANT_MODE,
    AUTOROLE_DELAY_SEC_KEY: 300,
    INTRO_CHANNEL_ID_KEY: -1,
}

# Log constants
ACTIV_ART_BOT = "activ-art-bot"
ACTIV_ART_BOT_LOGNAME = f"{ACTIV_ART_BOT}.log"


# Setup logging
def setup_logging():
    """Set up logging configuration."""
    LOG_DIR.mkdir(exist_ok=True)

    # Create logger
    logger = logging.getLogger(ACTIV_ART_BOT)
    logger.setLevel(logging.INFO)

    # Create file handler for logging
    file_handler = RotatingFileHandler(
        LOG_DIR / ACTIV_ART_BOT_LOGNAME, maxBytes=5 * 1024 * 1024, backupCount=5  # 5 MB
    )
    file_handler.setLevel(logging.INFO)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatter and add it to the handlers
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] - "
        "%(filename)s:%(lineno)s - %(funcName)s: %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Config management functions
def load_config() -> Dict[str, Any]:
    """Load configuration from config.json file."""
    if not CONFIG_FILE.exists():
        # Create default config if it doesn't exist
        default_config = {"guilds": {}}
        save_config(default_config)
        return default_config

    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger = logging.getLogger("bot")
        logger.error(f"Error decoding {CONFIG_FILE}. Using default config.")
        default_config = {"guilds": {}}
        save_config(default_config)
        return default_config


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to config.json file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


def get_guild_config(guild_id: int) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific guild."""
    config = load_config()
    return config["guilds"].get(str(guild_id))


def register_guild(guild_id: int) -> Dict[str, Any]:
    """Register a new guild with default configuration."""
    config = load_config()

    # Check if guild is already registered
    if str(guild_id) in config["guilds"]:
        return config["guilds"][str(guild_id)]

    # Add guild with default config
    config["guilds"][str(guild_id)] = DEFAULT_GUILD_CONFIG.copy()
    save_config(config)

    return config["guilds"][str(guild_id)]


def update_guild_config(guild_id: int, key: str, value: Any) -> None:
    """Update a specific configuration value for a guild."""
    config = load_config()

    # Ensure guild is registered
    if str(guild_id) not in config["guilds"]:
        register_guild(guild_id)

    # Update the value
    config["guilds"][str(guild_id)][key] = value
    save_config(config)


def remove_guild(guild_id: int) -> None:
    """Remove a guild from the configuration."""
    config = load_config()

    if str(guild_id) in config["guilds"]:
        del config["guilds"][str(guild_id)]
        save_config(config)


# Logger instance
logger = setup_logging()
