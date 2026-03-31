"""
Administration cog for Discord bot.
Handles auto-role assignment and guild configuration.
"""

import asyncio
import discord
from typing import Any
from discord import option
from discord.ext import commands
import re

from utils_dir.constants import (
    logger,
    get_guild_config,
    register_guild,
    update_guild_config,
    remove_guild,
)


from utils_dir.constants import (
    NONE_STR,
    AUTOROLE_TRIGGER_KEY,
    AUTOROLE_DELAY_SEC,
    AUTOROLE_DELAY_SEC_KEY,
    AUTOROLE_INSTANT_MODE,
    AUTOROLE_MESSAGE_MODE,
    INTRO_CHANNEL_ID_KEY,
    ADMIN_ROLE_IDS_KEY,
    ADMIN_CHANNEL_ID_KEY,
    VERIFIED_ROLE_IDS_KEY,
    COGS_DIR_NAME,
)

from utils_dir.messages import (
    GUILD_ONLY_ERROR,
    PERMISSION_ERROR,
    REGISTRATION_REQUIRED,
    REGISTRATION_SUCCESS,
    ROLE_ADDED_SUCCESS,
    SETTING_UPDATED,
    NO_VERIFIED_ROLES,
    INVALID_BEHAVIOR,
    NO_VALID_ROLES,
    MEMBER_ALREADY_VERIFIED,
    CONFIG_RESET,
    ROLE_ALREADY_IN_LIST,
    ROLE_NOT_FOUND,
    INVALID_ROLE_FORMAT,
    ADMIN_ONLY_ERROR,
    SUCCESS_EMOJI,
    ERROR_EMOJI,
    WARNING_EMOJI,
    ROLES_ASSIGNED,
    create_checklist_embed,
)


class Administration(commands.Cog):
    """Administration cog for handling auto-role assignment and guild configuration."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pending_role_assignments = {}  # Store pending role assignments

    async def cog_load(self):
        """Called when the cog is loaded."""
        logger.info("Administration cog loaded")

    # Helper methods
    def _has_permission(self, member: discord.Member) -> bool:
        """Check if a member has permission to use admin commands."""
        # Check for Administrator permission
        if member.guild_permissions.administrator:
            return True

        # Check for custom admin roles
        guild_config = get_guild_config(member.guild.id)
        if not guild_config or ADMIN_ROLE_IDS_KEY not in guild_config:
            return False

        admin_role_ids = guild_config[ADMIN_ROLE_IDS_KEY]
        return any(role.id in admin_role_ids for role in member.roles)

    async def _send_admin_notification(
        self, guild: discord.Guild, message: str
    ) -> None:
        """Send a notification to the guild's admin channel."""
        guild_config = get_guild_config(guild.id)
        if not guild_config or ADMIN_CHANNEL_ID_KEY not in guild_config:
            return

        admin_channel_id = guild_config[ADMIN_CHANNEL_ID_KEY]
        if admin_channel_id == -1:
            return

        try:
            channel = guild.get_channel(admin_channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                await channel.send(message)
        except Exception as e:
            logger.error(f"Failed to send admin notification in guild {guild.id}: {e}")

    async def _assign_roles(self, member: discord.Member) -> None:
        """Assign verified roles to a member."""
        guild_config = get_guild_config(member.guild.id)
        if not guild_config or VERIFIED_ROLE_IDS_KEY not in guild_config:
            return

        role_ids = guild_config[VERIFIED_ROLE_IDS_KEY]
        if not role_ids:
            return

        roles_to_add = []
        missing_roles = []

        for role_id in role_ids:
            role = member.guild.get_role(role_id)
            if role:
                roles_to_add.append(role)
            else:
                missing_roles.append(role_id)

        if missing_roles:
            logger.warning(f"Missing roles in guild {member.guild.id}: {missing_roles}")
            await self._send_admin_notification(
                member.guild, f"⚠️ Some verified roles are missing: {missing_roles}"
            )

        if not roles_to_add:
            return

        try:
            await member.add_roles(*roles_to_add, reason="Auto-verification")
            logger.info(
                f"Assigned verified roles to {member.id} in guild {member.guild.id}"
            )
        except discord.Forbidden:
            logger.error(
                f"Missing permissions to assign roles in guild {member.guild.id}"
            )
            await self._send_admin_notification(
                member.guild,
                f"❌ Failed to assign roles to {member.mention}: Missing permissions",
            )
        except Exception as e:
            logger.error(f"Error assigning roles in guild {member.guild.id}: {e}")
            await self._send_admin_notification(
                member.guild, f"❌ Failed to assign roles to {member.mention}: {str(e)}"
            )

    # Event listeners
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle member join event."""
        logger.info(f"Member {member.id} joined guild {member.guild.id}")

        # Check if guild is registered
        guild_config = get_guild_config(member.guild.id)
        if not guild_config:
            logger.info(f"Guild {member.guild.id} not registered, skipping auto-role")
            return

        # Check auto-role trigger
        trigger = guild_config.get(AUTOROLE_TRIGGER_KEY, AUTOROLE_INSTANT_MODE)

        if trigger == AUTOROLE_INSTANT_MODE:
            # Schedule delayed role assignment
            delay = guild_config.get(AUTOROLE_DELAY_SEC_KEY, AUTOROLE_DELAY_SEC)
            logger.info(f"Auto-assigning role(s) for {member.id} in {delay} seconds")

            # Store task reference to prevent garbage collection
            self.pending_role_assignments[member.id] = asyncio.create_task(
                self._delayed_role_assignment(member, delay)
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle message event for intro-message verification."""
        # Ignore bot messages
        if message.author.bot:
            return

        # Ignore non-guild originating messages
        if not message.guild:
            return

        # Check if author is a member of a guild
        if not isinstance(message.author, discord.Member):
            return

        member: discord.Member = message.author
        guild: discord.Guild = message.guild

        # Check if guild is registered
        guild_config = get_guild_config(guild.id)
        if not guild_config:
            return

        # HALT further processing if "intro-message" mode is not being used
        if guild_config.get(AUTOROLE_TRIGGER_KEY) != AUTOROLE_MESSAGE_MODE:
            return

        # Check if in the correct channel
        intro_channel_id = guild_config.get(INTRO_CHANNEL_ID_KEY, -1)
        if intro_channel_id == -1 or message.channel.id != intro_channel_id:
            return

        # Check message length
        if len(message.content) < 2:
            return

        # Assign roles
        await self._assign_roles(member)

    async def _delayed_role_assignment(self, member: discord.Member, delay: int):
        """Assign roles after a delay."""
        try:
            await asyncio.sleep(delay)
            await self._assign_roles(member)
        except Exception as e:
            logger.error(f"Error in delayed role assignment: {e}")
        finally:
            # Clean up task reference
            if member.id in self.pending_role_assignments:
                del self.pending_role_assignments[member.id]

    # Command group
    adm_group: discord.SlashCommandGroup = discord.SlashCommandGroup(
        name="adm",
        description="Administrative commands for bot configuration",
        guild_only=True,
    )

    @adm_group.command(
        name="register", description="REQUIRED: Register this guild to the application"
    )
    async def register_guild(
        self, ctx: discord.ApplicationContext, ephemeral: bool = True
    ):
        """Register the current guild with the bot."""
        if not ctx.guild:
            await ctx.respond(GUILD_ONLY_ERROR, ephemeral=True)
            return

        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond("Unauthorized to use this command.", ephemeral=True)
            return

        guild_id = ctx.guild_id
        assert guild_id is not None
        guild_config = get_guild_config(guild_id)

        if guild_config:
            await ctx.respond(REGISTRATION_SUCCESS, ephemeral=ephemeral)
            return

        register_guild(guild_id)
        logger.info(f"Guild {guild_id} registered")

        await ctx.respond(REGISTRATION_SUCCESS, ephemeral=ephemeral)

    @adm_group.command(
        name="add-verify-role",
        description="Add a role to the list of auto-roles granted upon verification",
    )
    @option("role", description="Role to add")
    async def add_verify_role_command(
        self, ctx: discord.ApplicationContext, role: str, ephemeral: bool = True
    ):
        """Add or update a role to the verified roles list."""
        if not ctx.guild:
            await ctx.respond(GUILD_ONLY_ERROR, ephemeral=True)
            return

        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(PERMISSION_ERROR, ephemeral=True)
            return

        guild_id = ctx.guild_id
        assert guild_id is not None

        # Ensure guild is registered
        guild_config = get_guild_config(guild_id)
        if not guild_config:
            guild_config = register_guild(guild_id)

        # Parse role ID from mention or direct ID
        role_id = None

        # Check if it's a mention
        mention_match = re.match(r"<@&(\d+)>", role)
        if mention_match:
            role_id = int(mention_match.group(1))
        else:
            # Check if it's a direct ID
            try:
                role_id = int(role)
            except ValueError:
                await ctx.respond(
                    INVALID_ROLE_FORMAT,
                    ephemeral=True,
                )
                return

        # Verify role exists
        discord_role = ctx.guild.get_role(role_id)
        if not discord_role:
            await ctx.respond(ROLE_NOT_FOUND.format(role_id=role_id), ephemeral=True)
            return

        # Update config
        verified_roles = guild_config.get("verified-role-ids", [])

        if role_id in verified_roles:
            await ctx.respond(
                ROLE_ALREADY_IN_LIST.format(
                    role_name=discord_role.name, list_type="verified"
                ),
                ephemeral=ephemeral,
            )
            return

        verified_roles.append(role_id)
        update_guild_config(guild_id, "verified-role-ids", verified_roles)

        logger.info(f"Added verified role {role_id} to guild {guild_id}")

        await ctx.respond(
            ROLE_ADDED_SUCCESS.format(
                role_name=discord_role.name, list_type="verified"
            ),
            ephemeral=ephemeral,
        )

    @adm_group.command(
        name="confirm-verify-roles",
        description="Remove any nonexistent auto-role roles",
    )
    async def confirm_verify_roles_command(
        self, ctx: discord.ApplicationContext, ephemeral: bool = False
    ):
        """Validate and clean up the verified roles list."""
        if not ctx.guild:
            await ctx.respond(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        guild_id = ctx.guild_id
        assert guild_id is not None

        # Ensure guild is registered
        guild_config = get_guild_config(guild_id)
        if not guild_config:
            await ctx.respond(
                "❌ This server is not registered. Use `/adm register` first.",
                ephemeral=True,
            )
            return

        # Get current roles
        verified_roles = guild_config.get("verified-role-ids", [])
        if not verified_roles:
            await ctx.respond(
                "No verified roles are configured for this server.", ephemeral=ephemeral
            )
            return

        # Check each role
        valid_roles = []
        removed_roles = []

        for role_id in verified_roles:
            role = ctx.guild.get_role(role_id)
            if role:
                valid_roles.append(role_id)
            else:
                removed_roles.append(role_id)

        # Update config if needed
        if removed_roles:
            update_guild_config(guild_id, "verified-role-ids", valid_roles)
            logger.info(f"Removed invalid roles from guild {guild_id}: {removed_roles}")

            await ctx.respond(
                f"✅ Removed {len(removed_roles)} invalid roles from the verified roles list.\n"
                f"Remaining valid roles: {len(valid_roles)}",
                ephemeral=ephemeral,
            )
        else:
            await ctx.respond(
                f"✅ All {len(valid_roles)} verified roles are valid.",
                ephemeral=ephemeral,
            )

    @adm_group.command(name="clear-settings")
    async def clear_settings(
        self, ctx: discord.ApplicationContext, ephemeral: bool = False
    ):
        """Reset guild configuration to default values."""
        if not ctx.guild:
            await ctx.respond(GUILD_ONLY_ERROR, ephemeral=True)
            return

        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(PERMISSION_ERROR, ephemeral=True)
            return

        guild_id = ctx.guild_id

        # Remove guild config and re-register with defaults
        assert guild_id is not None
        remove_guild(guild_id)
        register_guild(guild_id)
        logger.info(f"Reset configuration for guild {guild_id}")

        await ctx.respond(CONFIG_RESET, ephemeral=ephemeral)

    @adm_group.command(
        name="config", description="Display this server's current config"
    )
    async def config_command(
        self, ctx: discord.ApplicationContext, ephemeral: bool = True
    ):
        """Display current guild configuration."""
        if not ctx.guild:
            await ctx.respond(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        guild_id = ctx.guild_id

        # Get guild config
        assert guild_id is not None
        guild_config = get_guild_config(guild_id)
        if not guild_config:
            await ctx.respond(
                "❌ This server is not registered. Use `/adm register` first.",
                ephemeral=True,
            )
            return

        # Format config for display
        verified_roles = []
        for role_id in guild_config.get("verified-role-ids", []):
            role = ctx.guild.get_role(role_id)
            if role:
                verified_roles.append(f"{role.name} ({role_id})")
            else:
                verified_roles.append(f"Unknown Role ({role_id})")

        admin_roles = []
        for role_id in guild_config.get("admin-role-ids", []):
            role = ctx.guild.get_role(role_id)
            if role:
                admin_roles.append(f"{role.name} ({role_id})")
            else:
                admin_roles.append(f"Unknown Role ({role_id})")

        admin_channel_id = guild_config.get("admin-channel-id", -1)
        admin_channel = "None"
        if admin_channel_id != -1:
            channel = ctx.guild.get_channel(admin_channel_id)
            if channel:
                admin_channel = f"{channel.mention} ({admin_channel_id})"
            else:
                admin_channel = f"Unknown Channel ({admin_channel_id})"

        intro_channel_id = guild_config.get("intro-channel-id", -1)
        intro_channel = "None"
        if intro_channel_id != -1:
            channel = ctx.guild.get_channel(intro_channel_id)
            if channel:
                intro_channel = f"{channel.mention} ({intro_channel_id})"
            else:
                intro_channel = f"Unknown Channel ({intro_channel_id})"

        config_text = (
            "**Current Server Configuration**\n\n"
            f"**Verified Roles:** {', '.join(verified_roles) if verified_roles else NONE_STR}\n"
            f"**Admin Channel:** {admin_channel}\n"
            f"**Admin Roles:** {', '.join(admin_roles) if admin_roles else NONE_STR}\n"
            f"**Auto-Role Trigger:** {guild_config.get(AUTOROLE_TRIGGER_KEY, AUTOROLE_INSTANT_MODE)}\n"
            f"**Auto-Role Delay:** {guild_config.get(AUTOROLE_DELAY_SEC_KEY, AUTOROLE_DELAY_SEC)} seconds\n"
            f"**Intro Channel:** {intro_channel}"
        )

        await ctx.respond(config_text, ephemeral=ephemeral)

    @adm_group.command(
        name="set-verify-behavior-options",
        description="View available auto-role verification behavior options",
    )
    async def set_verify_behavior_options_command(
        self, ctx: discord.ApplicationContext, ephemeral: bool = True
    ):
        """View available verification behavior options."""
        if not ctx.guild:
            await ctx.respond(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        options_text = (
            "**Available Verification Behavior Options**\n\n"
            "**instant**\n"
            "- Assigns roles after a configurable delay when a user joins\n"
            "- Use `/adm set-verify-behavior instant` to enable\n"
            "- Configure delay with `/adm set-verify-delay <seconds>`\n\n"
            "**intro-message**\n"
            "- Assigns roles when a user posts in the designated intro channel\n"
            "- Message must be at least 2 characters long\n"
            "- Use `/adm set-verify-behavior intro-message` to enable\n"
            "- Configure intro channel with `/adm set-intro-channel <channel>`"
        )
        await ctx.respond(options_text, ephemeral=ephemeral)

    @adm_group.command(
        name="set-verify-behavior",
        description="Set the auto-role verification behavior",
    )
    @option(
        "behavior", description="Must be 'instant' or 'intro-message'", input_type=str
    )
    async def set_verify_behavior_command(
        self, ctx: discord.ApplicationContext, behavior: str, ephemeral: bool = False
    ):
        """Set the verification behavior for this server."""
        if not ctx.guild:
            await ctx.respond(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        guild_id = ctx.guild_id

        # Ensure guild is registered
        assert guild_id is not None
        guild_config = get_guild_config(guild_id)
        if not guild_config:
            guild_config = register_guild(guild_id)

        # Validate behavior
        if behavior not in [AUTOROLE_INSTANT_MODE, AUTOROLE_MESSAGE_MODE]:
            await ctx.respond(
                "❌ Invalid behavior. Use 'instant' or 'intro-message'.", ephemeral=True
            )
            return

        # Update config
        update_guild_config(guild_id, AUTOROLE_TRIGGER_KEY, behavior)

        logger.info(f"Set verification behavior to {behavior} for guild {guild_id}")

        # Additional instructions based on behavior
        additional_info = ""
        if behavior == AUTOROLE_INSTANT_MODE:
            delay = guild_config.get(AUTOROLE_DELAY_SEC_KEY, AUTOROLE_DELAY_SEC)
            additional_info = (
                f"\nRoles will be assigned {delay} seconds after a user joins."
            )
        elif behavior == AUTOROLE_MESSAGE_MODE:
            intro_channel_id = guild_config.get(INTRO_CHANNEL_ID_KEY, -1)
            if intro_channel_id == -1:
                additional_info = "\nNo intro channel is configured. Use `/adm set-intro-channel` to set one."
            else:
                channel = ctx.guild.get_channel(intro_channel_id)
                if channel:
                    additional_info = f"\nRoles will be assigned when users post in {channel.mention}."
                else:
                    additional_info = "\nConfigured intro channel not found. Use `/adm set-intro-channel` to set a valid one."

        await ctx.respond(
            f"✅ Verification behavior set to **{behavior}**.{additional_info}",
            ephemeral=ephemeral,
        )

    @adm_group.command(
        name="set-verify-delay",
        description="Set the delay (seconds) before auto-assigning roles in instant mode",
    )
    @option("seconds", description="Delay in seconds", input_type=float)
    async def set_verify_delay_command(
        self, ctx: discord.ApplicationContext, seconds: float, ephemeral: bool = False
    ):
        """Set the delay before assigning roles in instant mode."""
        if not ctx.guild:
            await ctx.respond(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        guild_id = ctx.guild_id

        # Ensure guild is registered
        assert guild_id is not None
        guild_config = get_guild_config(guild_id)
        if not guild_config:
            guild_config = register_guild(guild_id)

        # Validate seconds
        seconds = max(3, seconds)  # Force a minimum delay
        seconds = min(86400, seconds)  # Cap at 24 hours

        # Update config
        update_guild_config(guild_id, AUTOROLE_DELAY_SEC_KEY, seconds)

        logger.info(f"Set verification delay to {seconds} seconds for guild {guild_id}")

        await ctx.respond(
            f"✅ Verification delay set to **{seconds} seconds**.", ephemeral=ephemeral
        )

    @adm_group.command(
        name="set-intro-channel",
        description="Set the text channel for intro messages in intro-message mode",
    )
    @option("channel", description="Text channel where users should post introductions")
    async def set_intro_channel(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
        ephemeral: bool = False,
    ):
        """Set the channel for intro messages in intro-message mode."""
        if not ctx.guild:
            await ctx.respond(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        guild_id = ctx.guild_id

        # Ensure guild is registered
        assert guild_id is not None
        guild_config = get_guild_config(guild_id)
        if not guild_config:
            guild_config = register_guild(guild_id)

        # Update config
        update_guild_config(guild_id, INTRO_CHANNEL_ID_KEY, channel.id)

        logger.info(f"Set intro channel to {channel.id} for guild {guild_id}")

        # Additional info based on current behavior
        additional_info = ""
        if guild_config.get(AUTOROLE_TRIGGER_KEY) != AUTOROLE_MESSAGE_MODE:
            additional_info = "\n:warning: Note: Verification behavior is not set to `intro-message`. Use `/adm set-verify-behavior intro-message` to enable intro message verification."

        await ctx.respond(
            f"✅ Intro channel set to {channel.mention}.{additional_info}",
            ephemeral=ephemeral,
        )

    @adm_group.command(
        name="set-admin-channel", description="Set the channel for admin notifications"
    )
    @option(
        "channel", description="Channel for admin notifications. Can be ID or @channel"
    )
    async def set_admin_channel(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
        ephemeral: bool = False,
    ):
        """Set the channel for admin notifications."""
        if not ctx.guild:
            await ctx.respond(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        guild_id = ctx.guild_id

        # Ensure guild is registered
        assert guild_id is not None
        guild_config = get_guild_config(guild_id)
        if not guild_config:
            guild_config = register_guild(guild_id)

        # Update config
        assert guild_id is not None
        update_guild_config(guild_id, "admin-channel-id", channel.id)

        logger.info(f"Set admin channel to {channel.id} for guild {guild_id}")

        await ctx.respond(
            f"✅ Admin notification channel set to {channel.mention}.",
            ephemeral=ephemeral,
        )

    @adm_group.command(
        name="add-admin-role", description="Add a role that can use /adm commands"
    )
    @option("role", description="The role (ID or @mention) to allow /adm command usage")
    async def add_admin_role(
        self, ctx: discord.ApplicationContext, role: str, ephemeral: bool = False
    ):
        """Add a role that can use admin commands."""
        if not ctx.guild:
            await ctx.respond(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        assert isinstance(ctx.author, discord.Member)
        if not ctx.author.guild_permissions.administrator:
            await ctx.respond(
                "❌ Only users with Administrator permission can add admin roles.",
                ephemeral=True,
            )
            return

        guild_id = ctx.guild_id

        # Ensure guild is registered
        assert guild_id is not None
        guild_config = get_guild_config(guild_id)
        if not guild_config:
            guild_config = register_guild(guild_id)

        # Parse role ID from mention or direct ID
        role_id = None

        # Check if it's a mention
        mention_match = re.match(r"<@&(\d+)>", role)
        if mention_match:
            role_id = int(mention_match.group(1))
        else:
            # Check if it's a direct ID
            try:
                role_id = int(role)
            except ValueError:
                await ctx.respond(
                    "❌ Invalid role format. Please use a role ID or @mention.",
                    ephemeral=True,
                )
                return

        # Verify role exists
        discord_role = ctx.guild.get_role(role_id)
        if not discord_role:
            await ctx.respond(
                f"❌ Role with ID {role_id} not found in this server.", ephemeral=True
            )
            return

        # Update config
        admin_roles: list = guild_config.get(ADMIN_ROLE_IDS_KEY, [])

        if role_id in admin_roles:
            await ctx.respond(
                f"Role {discord_role.name} is already in the admin roles list.",
                ephemeral=ephemeral,
            )
            return

        admin_roles.append(role_id)
        assert guild_id is not None
        update_guild_config(guild_id, ADMIN_ROLE_IDS_KEY, admin_roles)

        logger.info(f"Added admin role {role_id} to guild {guild_id}")

        await ctx.respond(
            f"✅ Added {discord_role.name} to the admin roles list.",
            ephemeral=ephemeral,
        )

    @adm_group.command(
        name="autorole-checklist",
        description="Check if autorole setup steps are complete",
    )
    async def autorole_checklist(
        self, ctx: discord.ApplicationContext, ephemeral: bool = True
    ):
        """Check if autorole setup steps are complete."""
        if not ctx.guild:
            await ctx.respond(GUILD_ONLY_ERROR, ephemeral=True)
            return

        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(PERMISSION_ERROR, ephemeral=True)
            return

        guild_id = ctx.guild_id
        assert guild_id is not None
        guild_config = get_guild_config(guild_id)

        if not guild_config:
            await ctx.respond(REGISTRATION_REQUIRED, ephemeral=ephemeral)
            return

        # Check registration status
        registration_status = f"{SUCCESS_EMOJI} Server is registered"

        # Check verified roles
        verified_roles = guild_config.get(VERIFIED_ROLE_IDS_KEY, [])
        valid_roles = []
        for role_id in verified_roles:
            role = ctx.guild.get_role(role_id)
            if role:
                valid_roles.append(role)

        verified_roles_status = (
            f"{SUCCESS_EMOJI} Verified roles configured"
            if valid_roles
            else f"{ERROR_EMOJI} No verified roles configured"
        )
        verified_roles_detail = (
            f"{len(valid_roles)} role(s) configured"
            if valid_roles
            else "Use `/adm add-verify-role` to add roles"
        )

        # Check admin channel
        admin_channel_id = guild_config.get(ADMIN_CHANNEL_ID_KEY, -1)
        admin_channel = (
            ctx.guild.get_channel(admin_channel_id) if admin_channel_id != -1 else None
        )
        admin_channel_status = (
            f"{SUCCESS_EMOJI} Admin channel configured"
            if admin_channel
            else f"{ERROR_EMOJI} No admin channel configured"
        )
        admin_channel_detail = (
            f"{admin_channel.mention}"
            if admin_channel
            else "Use `/adm set-admin-channel` to set a channel"
        )

        # Check verification mode
        trigger = guild_config.get(AUTOROLE_TRIGGER_KEY, AUTOROLE_INSTANT_MODE)
        trigger_status = f"{SUCCESS_EMOJI} Verification mode configured"
        trigger_detail = f"Mode: {trigger}"

        # Check mode-specific requirements
        mode_specific_status = ""
        mode_specific_detail = ""

        if trigger == AUTOROLE_INSTANT_MODE:
            delay = guild_config.get(AUTOROLE_DELAY_SEC_KEY, AUTOROLE_DELAY_SEC)
            mode_specific_status = f"{SUCCESS_EMOJI} Delay configured"
            mode_specific_detail = f"Delay: {delay} seconds"
        elif trigger == AUTOROLE_MESSAGE_MODE:
            intro_channel_id = guild_config.get(INTRO_CHANNEL_ID_KEY, -1)
            intro_channel = (
                ctx.guild.get_channel(intro_channel_id)
                if intro_channel_id != -1
                else None
            )
            mode_specific_status = (
                f"{SUCCESS_EMOJI} Intro channel configured"
                if intro_channel
                else f"{ERROR_EMOJI} No intro channel configured"
            )
            mode_specific_detail = (
                f"{intro_channel.mention}"
                if intro_channel
                else "Use `/adm set-intro-channel` to set a channel"
            )

        # Overall status
        is_ready = bool(valid_roles) and (
            (trigger == AUTOROLE_INSTANT_MODE)
            or (trigger == AUTOROLE_MESSAGE_MODE and intro_channel is not None)
        )

        # Create embed using the utility function
        embed = create_checklist_embed(
            registration_status=registration_status,
            verified_roles_status=verified_roles_status,
            verified_roles_detail=verified_roles_detail,
            admin_channel_status=admin_channel_status,
            admin_channel_detail=admin_channel_detail,
            trigger_status=trigger_status,
            trigger_detail=trigger_detail,
            mode_specific_status=mode_specific_status,
            mode_specific_detail=mode_specific_detail,
            trigger_name=trigger,
            is_ready=is_ready,
        )

        await ctx.respond(embed=embed, ephemeral=ephemeral)

    @adm_group.command(name="verify-member", description="Manually verify a member")
    @option("member", description="The member to verify")
    async def verify_member(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        ephemeral: bool = True,
    ):
        """Manually verify a member by assigning verified roles."""
        if not ctx.guild:
            await ctx.respond(GUILD_ONLY_ERROR, ephemeral=True)
            return

        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(PERMISSION_ERROR, ephemeral=True)
            return

        guild_id = ctx.guild_id
        assert guild_id is not None
        guild_config = get_guild_config(guild_id)

        if not guild_config:
            await ctx.respond(REGISTRATION_REQUIRED, ephemeral=ephemeral)
            return

        # Check if verified roles are configured
        verified_roles = guild_config.get(VERIFIED_ROLE_IDS_KEY, [])
        if not verified_roles:
            await ctx.respond(NO_VERIFIED_ROLES, ephemeral=ephemeral)
            return

        # Defer response to allow time for role assignment
        await ctx.defer(ephemeral=ephemeral)

        # Get roles to assign
        roles_to_add = []
        missing_roles = []
        already_has_roles = []

        for role_id in verified_roles:
            role = ctx.guild.get_role(role_id)
            if role:
                if role in member.roles:
                    already_has_roles.append(role)
                else:
                    roles_to_add.append(role)
            else:
                missing_roles.append(role_id)

        # Log missing roles if any
        if missing_roles:
            logger.warning(f"Missing roles in guild {ctx.guild.id}: {missing_roles}")
            await self._send_admin_notification(
                ctx.guild,
                WARNING_EMOJI + f" Some verified roles are missing: {missing_roles}",
            )

        # If no roles to add, respond accordingly
        if not roles_to_add:
            if already_has_roles:
                await ctx.followup.send(
                    MEMBER_ALREADY_VERIFIED.format(member=member.mention),
                    ephemeral=ephemeral,
                )
            else:
                await ctx.followup.send(NO_VALID_ROLES, ephemeral=ephemeral)
            return

        # Assign roles
        success = True
        error_message = ""

        try:
            await member.add_roles(
                *roles_to_add, reason=f"Manual verification by {ctx.author}"
            )
            logger.info(
                f"Manually assigned verified roles to {member.id} in guild {ctx.guild.id} by {ctx.author.id}"
            )
        except discord.Forbidden:
            success = False
            error_message = "Missing permissions to assign roles"
            logger.error(f"Missing permissions to assign roles in guild {ctx.guild.id}")
            await self._send_admin_notification(
                ctx.guild,
                f"{ERROR_EMOJI} Failed to assign roles to {member.mention}: Missing permissions",
            )
        except Exception as e:
            success = False
            error_message = str(e)
            logger.error(f"Error assigning roles in guild {ctx.guild.id}: {e}")
            await self._send_admin_notification(
                ctx.guild,
                f"{ERROR_EMOJI} Failed to assign roles to {member.mention}: {str(e)}",
            )

        # Respond with result
        if success:
            role_names = ", ".join([role.name for role in roles_to_add])
            already_has_message = ""
            if already_has_roles:
                already_has_message = (
                    f"\n(Member already had {len(already_has_roles)} verified role(s))"
                )

            await ctx.followup.send(
                ROLES_ASSIGNED.format(
                    count=len(roles_to_add),
                    member=member.mention,
                    role_names=role_names,
                )
                + already_has_message,
                ephemeral=ephemeral,
            )
        else:
            await ctx.followup.send(
                f"{ERROR_EMOJI} Failed to assign roles to {member.mention}: {error_message}",
                ephemeral=ephemeral,
            )

    @adm_group.command(
        name="send-msg", description="Send a message to <channel> via Kaede"
    )
    @option("channel", description="#text-channel to send message to")
    @option("text", description="Message to send")
    async def send_msg(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
        *,
        text: str,
    ):
        """
        Have the bot send a message to a target text channel.

        Critical: Do not log text. Only attempt to send.
        """
        assert ctx.guild is not None

        # Verify administrative permission
        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(PERMISSION_ERROR, ephemeral=True)
            return

        # Attempt to send message to target channel
        try:
            await channel.send(text)
            await ctx.respond(f"{SUCCESS_EMOJI} Message sent.", ephemeral=True)
        except Exception as e:
            logger.exception("Exception: ")
            await self._send_admin_notification(
                ctx.guild,
                f"{ERROR_EMOJI} Failed to send message to channel {channel.mention}: {str(e)}",
            )

    @adm_group.command(
        name="send-msg-custom",
        description="Send a multi-line message to <channel> via Kaede",
    )
    @option("channel", description="#text-channel to send message to")
    async def send_msg_custom(
        self, ctx: discord.ApplicationContext, channel: discord.TextChannel
    ):
        """
        Have the bot send a multi-line message to a target text channel.

        Critical: Do not log text. Only attempt to send.
        """

        # Helper
        def check(m: discord.Message):
            # Ensure message channel and author are same as command invoker
            if ctx.channel is None:
                return False
            return ctx.author == m.author and ctx.channel.id == m.channel.id

        # Verify administrative permission
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        if not self._has_permission(ctx.author):
            await ctx.respond(PERMISSION_ERROR, ephemeral=True)
            return

        # Prompt the user: "Hey! Reply with the message you would like to send:"
        user_prompt: str = (
            f"Hey {ctx.author.display_name}! REPLY to me with the message you would like to send: "
        )
        try:
            await ctx.respond(user_prompt)
        except Exception:
            logger.exception("Exception: ")
            return

        # Await user's reply/response
        content: str | None = None
        try:
            user_response: discord.Message | None = await self.bot.wait_for(
                "message", check=check, timeout=60.0
            )
            assert user_response is not None

            content = user_response.content
            assert content is not None
        except Exception:
            logger.exception("Exception: ")
            return await ctx.respond(
                f"{ERROR_EMOJI} Ah-something went wrong...try again?"
            )

        # Attempt to send the message
        try:
            await channel.send(user_response.content)
            await ctx.respond(f"{SUCCESS_EMOJI} Message sent.", ephemeral=True)
        except Exception:
            logger.exception("Exception: ")
            await self._send_admin_notification(
                ctx.guild,
                f"{ERROR_EMOJI} Ah-I couldn't send your message...please check logs! :persevere: or try again!",
            )

    @adm_group.command(name="reload-ext", description="Reload a bot extension")
    @option("ext", description="Extension to reload (e.g., 'admin' for cogs.admin)")
    async def reload_ext(self, ctx: discord.ApplicationContext, ext: str):
        """
        Administrative command to reload a bot extension (Cog) to ingest newest code changes.
        """
        try:
            target_extension: str = f"{COGS_DIR_NAME}.{ext}"
            if target_extension not in self.bot.extensions:
                raise FileNotFoundError(
                    f"{WARNING_EMOJI} Extension '{target_extension}' could not be found. Please verify extension name."
                )
            self.bot.reload_extension(target_extension)
            await ctx.respond(f"{SUCCESS_EMOJI} Extension reloaded.", ephemeral=True)
        except Exception:
            logger.exception("Exception: ")


def setup(bot: commands.Bot):
    bot.add_cog(Administration(bot))
