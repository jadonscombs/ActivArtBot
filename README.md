# ActivArtBot

A simple Discord bot for self-hosting that supports customized auto-role behavior. Comes with intuitive administrative commands and zero-config logging support. More features are to be added. 

## Features

- Auto-assign roles to new members with configurable behavior:
  - Instant mode: Assign roles after a configurable delay
  - Intro-message mode: Assign roles after user posts in a designated channel
- Guild-specific configuration
- Admin commands for managing verification settings
- Detailed error handling and logging

## Requirements

- Python 3.11.7 or higher
- py-cord 2.7.1
- python-dotenv

## Setup

1. Clone this repository
2. Create a virtual environment and activate it:
   ```
   python -m venv .venv
   # On Windows
   .venv\Scripts\activate
   # On macOS/Linux
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Create a `.env` file with your Discord bot token:
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   ```
5. Run the bot:
   ```
   python app.py
   ```

## Bot Configuration

Before using the bot, you need to:

1. Invite the bot to your server with appropriate permissions (Manage Roles, Read Messages, Send Messages)
2. Register your server with the bot using `/adm register`
3. Add verification roles using `/adm add-verify-role`
4. Configure verification behavior using `/adm set-verify-behavior`

## Available Commands

All commands are under the `/adm` group:

- `/adm register` - Register the current server with the bot
- `/adm add-verify-role` - Add a role to the verified roles list
- `/adm confirm-verify-roles` - Validate and clean up the verified roles list
- `/adm clear-settings` - Reset server configuration to defaults
- `/adm config` - Display current server configuration
- `/adm set-verify-behavior-options` - View available verification behavior options
- `/adm set-verify-behavior <behavior>` - Set verification behavior
- `/adm set-verify-delay <seconds>` - Set delay before assigning roles
- `/adm set-intro-channel <channel>` - Set channel for intro messages
- `/adm set-admin-channel <channel>` - Set channel for admin notifications
- `/adm add-admin-role <role>` - Add a role that can use admin commands
- `/adm autorole-checklist` - Check if autorole setup steps are complete
- `/adm verify-member <member>` - Manually verify a member by assigning verified roles

## Permissions

By default, only users with the Administrator permission can use admin commands. You can add additional roles that can use admin commands with `/adm add-admin-role`.

## Logging

The bot logs all actions to both the console and log files in the `logs` directory. Log files are rotated when they reach 5 MB, with a maximum of 5 backup files.

## Configuration File

The bot stores configuration in a `config.json` file with the following structure:

```json
{
    "guilds": {
        "guild_id": {
            "verified-role-ids": [role_id1, role_id2, ...],
            "admin-channel-id": channel_id,
            "admin-role-ids": [role_id1, role_id2, ...],
            "auto-role-trigger": "instant",
            "auto-role-delay-sec": 300,
            "intro-channel-id": channel_id
        }
    }
}
```

It's recommended to use the bot commands to manage this configuration rather than editing the file directly.