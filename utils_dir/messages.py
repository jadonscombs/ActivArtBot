"""
Common message patterns and formatting utilities for the Discord bot.
"""

import discord
from typing import Optional, Dict, Any

# Error messages
GUILD_ONLY_ERROR = "This command can only be used in a server."
PERMISSION_ERROR = "You don't have permission to use this command."
ADMIN_ONLY_ERROR = "❌ Only users with Administrator permission can add admin roles."
REGISTRATION_REQUIRED = "❌ This server is not registered. Use `/adm register` first."
INVALID_ROLE_FORMAT = "❌ Invalid role format. Please use a role ID or @mention."
ROLE_NOT_FOUND = "❌ Role with ID {role_id} not found in this server."
NO_VERIFIED_ROLES = "❌ No verified roles are configured for this server. Use `/adm add-verify-role` to add roles."
INVALID_BEHAVIOR = "❌ Invalid behavior. Use 'instant' or 'intro-message'."
NO_VALID_ROLES = "❌ No valid roles to assign."

# Success messages
REGISTRATION_SUCCESS = "✅ Server registered successfully!"
ROLE_ADDED_SUCCESS = "✅ Added {role_name} to the {list_type} roles list."
SETTING_UPDATED = "✅ {setting_name} set to **{value}**."
ROLES_ASSIGNED = "✅ Successfully assigned {count} role(s) to {member}: {role_names}"
MEMBER_ALREADY_VERIFIED = "✅ {member} already has all configured verified roles."
CONFIG_RESET = "✅ Server configuration has been reset to default values."

# Warning messages
MISSING_ROLES_WARNING = "⚠️ Some verified roles are missing: {missing_roles}"
ROLE_ALREADY_IN_LIST = "Role {role_name} is already in the {list_type} roles list."

# Status indicators
SUCCESS_EMOJI = "✅"
ERROR_EMOJI = "❌"
WARNING_EMOJI = "⚠️"

# Formatting templates
CONFIG_DISPLAY_TEMPLATE = """**Current Server Configuration**

**Verified Roles:** {verified_roles}
**Admin Channel:** {admin_channel}
**Admin Roles:** {admin_roles}
**Auto-Role Trigger:** {trigger}
**Auto-Role Delay:** {delay} seconds
**Intro Channel:** {intro_channel}
"""

OPTIONS_DISPLAY_TEMPLATE = """**Available Verification Behavior Options**

**instant**
- Assigns roles after a configurable delay when a user joins
- Use `/adm set-verify-behavior instant` to enable
- Configure delay with `/adm set-verify-delay <seconds>`

**intro-message**
- Assigns roles when a user posts in the designated intro channel
- Message must be at least 2 characters long
- Use `/adm set-verify-behavior intro-message` to enable
- Configure intro channel with `/adm set-intro-channel <channel>`
"""


# Error response functions
def guild_only_error(ctx: discord.ApplicationContext) -> None:
    """Respond with guild-only error message."""
    return ctx.respond(GUILD_ONLY_ERROR, ephemeral=True)


def permission_error(ctx: discord.ApplicationContext) -> None:
    """Respond with permission error message."""
    return ctx.respond(PERMISSION_ERROR, ephemeral=True)


def registration_required_error(
    ctx: discord.ApplicationContext, ephemeral: bool = True
) -> None:
    """Respond with registration required error message."""
    return ctx.respond(REGISTRATION_REQUIRED, ephemeral=ephemeral)


# Success response functions
def registration_success(
    ctx: discord.ApplicationContext, ephemeral: bool = True
) -> None:
    """Respond with registration success message."""
    return ctx.respond(REGISTRATION_SUCCESS, ephemeral=ephemeral)


def role_added_success(
    ctx: discord.ApplicationContext,
    role_name: str,
    list_type: str,
    ephemeral: bool = True,
) -> None:
    """Respond with role added success message."""
    return ctx.respond(
        ROLE_ADDED_SUCCESS.format(role_name=role_name, list_type=list_type),
        ephemeral=ephemeral,
    )


def setting_updated_success(
    ctx: discord.ApplicationContext,
    setting_name: str,
    value: Any,
    ephemeral: bool = True,
) -> None:
    """Respond with setting updated success message."""
    return ctx.respond(
        SETTING_UPDATED.format(setting_name=setting_name, value=value),
        ephemeral=ephemeral,
    )


# Embed creation functions
def create_checklist_embed(
    registration_status: str,
    verified_roles_status: str,
    verified_roles_detail: str,
    admin_channel_status: str,
    admin_channel_detail: str,
    trigger_status: str,
    trigger_detail: str,
    mode_specific_status: Optional[str] = None,
    mode_specific_detail: Optional[str] = None,
    trigger_name: Optional[str] = None,
    is_ready: bool = False,
) -> discord.Embed:
    """Create a standardized checklist embed for configuration status."""
    embed = discord.Embed(
        title="Autorole Configuration Checklist",
        description="Status of autorole configuration for this server",
        color=discord.Color.blue(),
    )

    embed.add_field(name="Registration", value=f"{registration_status}", inline=False)
    embed.add_field(
        name="Verified Roles",
        value=f"{verified_roles_status}\n{verified_roles_detail}",
        inline=False,
    )
    embed.add_field(
        name="Admin Channel",
        value=f"{admin_channel_status}\n{admin_channel_detail}",
        inline=False,
    )
    embed.add_field(
        name="Verification Mode",
        value=f"{trigger_status}\n{trigger_detail}",
        inline=False,
    )

    if mode_specific_status and trigger_name:
        embed.add_field(
            name=f"{trigger_name.capitalize()} Mode Settings",
            value=f"{mode_specific_status}\n{mode_specific_detail}",
            inline=False,
        )

    overall_status = (
        f"{SUCCESS_EMOJI} Autorole is properly configured and ready to use!"
        if is_ready
        else f"{ERROR_EMOJI} Autorole configuration is incomplete"
    )
    embed.add_field(name="Overall Status", value=overall_status, inline=False)

    embed.set_footer(text="Use /adm config to see all configuration details")

    return embed


def create_config_embed(
    guild_config: Dict[str, Any],
    verified_roles: str,
    admin_roles: str,
    admin_channel: str,
    intro_channel: str,
) -> discord.Embed:
    """Create a standardized embed for displaying configuration."""
    from utils_dir.constants import (
        AUTOROLE_TRIGGER_KEY,
        AUTOROLE_INSTANT_MODE,
        AUTOROLE_DELAY_SEC_KEY,
        AUTOROLE_DELAY_SEC,
    )

    embed = discord.Embed(
        title="Server Configuration",
        description="Current configuration for this server",
        color=discord.Color.blue(),
    )

    embed.add_field(name="Verified Roles", value=verified_roles, inline=False)
    embed.add_field(name="Admin Channel", value=admin_channel, inline=False)
    embed.add_field(name="Admin Roles", value=admin_roles, inline=False)
    embed.add_field(
        name="Auto-Role Trigger",
        value=guild_config.get(AUTOROLE_TRIGGER_KEY, AUTOROLE_INSTANT_MODE),
        inline=False,
    )
    embed.add_field(
        name="Auto-Role Delay",
        value=f"{guild_config.get(AUTOROLE_DELAY_SEC_KEY, AUTOROLE_DELAY_SEC)} seconds",
        inline=False,
    )
    embed.add_field(name="Intro Channel", value=intro_channel, inline=False)

    return embed
