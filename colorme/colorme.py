import asyncio
import discord
import distinctipy
import logging
import re
import webcolors
from typing import Optional, Union, Tuple, Dict, List

from discord.ext import tasks
from redbot.core import Config, app_commands, commands
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from .colors import names, hexes

log = logging.getLogger('red.colorme')


class ColorMe(commands.Cog):
    """Custom ColorMe Cog."""

    error_message = (
        '⛔ Not a valid color code. Use Hex, CSS3 Name or Discord Name.\n'
        '**Examples:** `2ecc71` or `#009966` or `gold` or `dark_purple`\n'
        '<https://www.w3.org/TR/css-color-3/#svg-color>\n'
        '<https://discordpy.readthedocs.io/en/latest/api.html#colour>'
    )

    guild_default = {
        'enabled': False,
        'blocked_roles': [],
    }

    color_info_url = 'https://www.color-hex.com/color/'
    prefix = 'c:'

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        self.cleanup_roles.start()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.cleanup_roles.cancel()

    @tasks.loop(minutes=30.0)
    async def cleanup_roles(self):
        await self.bot.wait_until_ready()
        log.info('%s: Cleanup Roles Task Run', self.__cog_name__)
        all_guilds: Dict[int, dict] = await self.config.all_guilds()
        async for guild_id, data in AsyncIter(all_guilds.items(), delay=2, steps=20):
            if not data['enabled']:
                continue
            guild: discord.Guild = self.bot.get_guild(int(guild_id))
            if not guild:
                log.warning('404 - Guild Not Found: %s', guild_id)
                continue
            async for role in AsyncIter(guild.roles, delay=2, steps=20):
                role: discord.Role
                if role.name.startswith(self.prefix):
                    if len(role.members) == 0:
                        log.debug('Guild "%s" Delete Color Role %s', guild.name, role.name)
                        await role.delete(reason='Cleanup Color Role')

    @staticmethod
    def color_converter(hex_or_color: str, prefix: Optional[str] = '0x') -> Optional[str]:
        """
        Used for user input on color
        Input:    Name, discord.Color name, CSS3 color name, 0xFFFFFF, #FFFFFF, FFFFFF
        Output:   0xFFFFFF or {prefix}FFFFFF
        """
        log.debug('prefix: %s', prefix)
        log.debug('hex_or_color: %s', hex_or_color)

        # 0xFFFFFF to {prefix}FFFFFF
        if hex_or_color.lower().startswith('0x'):
            hex_match = re.match(r'0x[a-f0-9]{6}', hex_or_color.lower())
            if hex_match:
                log.debug('-- 0x --')
                return f"{prefix}{hex_or_color.replace('0x', '')}"

        # #FFFFFF and FFFFFF to {prefix}FFFFFF
        hex_match = re.match(r'#?[a-f0-9]{6}', hex_or_color.lower())
        if hex_match:
            log.debug('-- hex --')
            return f"{prefix}{hex_or_color.lstrip('#')}"

        # int to {prefix}FFFFFF
        if hex_or_color.isdigit():
            newhex = '{0:06X}'.format(int(hex_or_color))
            if len(newhex) == 6:
                log.debug('-- int --')
                return f"{prefix}{newhex}"

        # discord.Color to {prefix}FFFFFF
        if hasattr(discord.Color, hex_or_color):
            log.debug('-- discord --')
            hex_code = str(getattr(discord.Color, hex_or_color.replace(' ', '_'))())
            return hex_code.replace('#', prefix)

        # CSS3 color name to {prefix}FFFFFF
        try:
            hex_code = webcolors.name_to_hex(hex_or_color)
            log.debug('-- css3 --')
            return hex_code.replace('#', prefix)
        except ValueError:
            pass

        # colors.py names to {prefix}FFFFFF
        if hex_or_color.lower() in names:
            log.debug('-- names --')
            return f"{prefix}{names[hex_or_color.lower()]}"

    # @commands.Cog.listener()
    # async def on_member_join(self, member: discord.Member):
    #     # wait for stickyroles to be applied
    #     await asyncio.sleep(10.0)
    #     guild: discord.Guild = member.guild
    #     config = await self.config.guild(guild).all()
    #     if not config['enabled']:
    #         return
    #
    #     log.debug('member.accent_color: %s', member.accent_color)
    #     log.debug('member.color: %s', member.color)
    #     member_color = member.accent_color or member.color or None
    #     log.debug('member_color: %s', member_color)
    #     color = self.color_converter(str(member_color))
    #     log.debug('color: %s', color)
    #     colorhex = color.replace('0x', '')
    #     log.debug('colorhex: %s', colorhex)
    #     role_name = f'{self.prefix}{colorhex}'
    #     log.debug('role_name: %s', role_name)
    #
    #     if colorhex == '000000':
    #         log.debug('%s has default color: %s', member.name, member_color)
    #         return
    #
    #     # Check if already has a color role or blocked_roles
    #     blocked_roles = await self.config.guild(guild).blocked_roles()
    #     for role in member.roles:
    #         if role.id in blocked_roles:
    #             log.debug('%s has blocked role: %s', member.name, role.name)
    #             return
    #         if role.name.startswith(self.prefix):
    #             log.debug('%s already has color role: %s', member.name, role.name)
    #             await member.remove_roles(role, reason='Remove Color Role')
    #             return
    #
    #     # Get or create new color role
    #     log.debug('role_name: %s', role_name)
    #     role: discord.Role = discord.utils.get(guild.roles, name=role_name)
    #     if not role:
    #         role: discord.Role = await guild.create_role(
    #             reason='Create Color Role',
    #             name=role_name,
    #             colour=discord.Colour(int(color, 16)),
    #             permissions=discord.Permissions.none(),
    #         )
    #         log.debug('Created new role: %s - %s', role.id, role.name)
    #
    #     # Add color role to user
    #     await member.add_roles(role, reason='Add Color Role')
    #     log.debug('Added Role %s to User %s', role.name, member.name)

    async def gen_embed(self, colorhex: str) -> discord.Embed:
        name = hexes[colorhex] if colorhex in hexes else 'Unknown'
        log.debug('name: %s', name)
        log.debug('colorhex: %s', colorhex)
        # log.debug('description: %s', description)
        # description = (
        #     f'Hex: **#{colorhex}**'
        #     f'Name: **{name}**'
        # )
        # description = 'Test'
        embed = discord.Embed(
            color=discord.Color(int(colorhex, 16)),
            title=name,
            url=f'{self.color_info_url}{colorhex}',
            # description=description,
        )
        embed.add_field(name='Hex', value=f'`#{colorhex}`')
        embed.add_field(name='Name', value=f'{name}')
        # embed.set_author(name=f'@{user.display_name or user.name}')
        return embed

    @commands.hybrid_command(name='hex')
    @app_commands.describe(color='Hex Value, CSS Name, or Discord Color Name')
    async def hex_command(self, ctx: commands.Context,
                          user: Optional[Union[discord.Member, discord.User]], *,
                          color: Optional[str] = None):
        """Get Color Name from <color> or <user>.
        `color` must be a hex, css, or Discord color.
        `user` Discord username, mention, or backslash \\ mention
        Examples: `2ecc71` or `#009966` or `gold` or `dark_purple`
        <https://www.w3.org/TR/css-color-3/#svg-color>
        """
        user: discord.Member
        if not color and not user:
            return await ctx.send_help()

        log.debug(0)
        if not user:
            log.debug(1)
            m = re.search('[0-9]{8,24}', color)
            if m and m.group(0):
                log.debug(10)
                user_id = int(m.group(0))
                user = discord.utils.get(ctx.guild.members, id=user_id)
            else:
                log.debug(11)
                user = discord.utils.get(ctx.guild.members, name=color)

            for mention in ctx.message.mentions:
                if mention.id != self.bot.user.id:
                    user = mention
                    break

        if user:
            log.debug(2)
            colorhex = None
            for role in user.roles:
                if role.name.startswith(self.prefix):
                    colorhex = role.name.replace(self.prefix, '')
                    break
            if not colorhex:
                log.debug(3)
                msg = f'⛔ No Color Roles found for user: {user.mention}'
                return await ctx.send(msg, ephemeral=True, delete_after=30,
                                      allowed_mentions=discord.AllowedMentions.none())
        else:
            log.debug(4)
            colorhex = self.color_converter(color, None)

        # member = None
        # if isinstance(color_or_user, discord.Member):
        #     member = color_or_user
        # else:
        #     member: discord.Member = discord.utils.get(ctx.guild.members, username=color_or_user)
        # if member:
        #     colorhex = None
        #     for role in member.roles:
        #         if role.name.startswith(self.prefix):
        #             colorhex = role.name.replace(self.prefix, '')
        #             break
        #     if not colorhex:
        #         msg = f'⛔ No Color Roles found for user: {user.mention}'
        #         return await ctx.send(msg, ephemeral=True, delete_after=30,
        #                               allowed_mentions=discord.AllowedMentions.none())
        #
        # colorhex = self.color_converter(color_or_user, None)

        # member: discord.Member = discord.utils.get(ctx.guild.members, username=color_or_user)
        # if member:
        #     colorhex = None
        #     for role in member.roles:
        #         if role.name.startswith(self.prefix):
        #             colorhex = role.name.replace(self.prefix, '')
        #             break
        #     if not colorhex:
        #         msg = f'No Color Roles found for user: {member}'
        #         await ctx.send(msg, ephemeral=True, delete_after=30)
        #         return
        #     name = hexes[colorhex] if colorhex in hexes else 'unknown'
        #     msg = (
        #         f'{member} is using hex `{colorhex}` called **{name}**\n'
        #         f'{self.color_info_url}{colorhex}'
        #     )
        #     await ctx.send(msg, ephemeral=True, delete_after=30)
        #     return
        # color: str = color_or_user
        # colorhex = self.color_converter(color, None)

        log.debug('colorhex: %s', colorhex)
        if not colorhex:
            return await ctx.send(self.error_message, ephemeral=True, delete_after=30)

        log.debug(5)
        embed = await self.gen_embed(colorhex)
        if user:
            msg = f'{user.mention} has color hex `#{colorhex}`'
        else:
            msg = f'Color {color} has color hex `#{colorhex}`'
        await ctx.send(msg, embed=embed, ephemeral=True, delete_after=300)

    @commands.hybrid_command(name='color')
    @commands.guild_only()
    @commands.cooldown(5, 10, commands.BucketType.user)
    @commands.max_concurrency(1, commands.BucketType.user)
    @app_commands.describe(color='Optional: Hex Value, CSS Name, or Discord Color Name')
    async def color_command(self, ctx: commands.Context, *, color: str):
        """Change the color of your name.
        **color** must be a hex, css, or Discord color.
        Examples: `2ecc71` or `#009966` or `gold` or `dark_purple`
        <https://www.w3.org/TR/css-color-3/#svg-color>
        """
        member = ctx.author
        guild = ctx.guild

        # Check if color command is enabled in guild
        enabled = await self.config.guild(guild).enabled()
        if not enabled:
            msg = '⛔ Color Not Enabled in this Guild. Contact Server Manager to Enable.'
            return await ctx.send(msg, ephemeral=True, delete_after=30)

        # Remove color if no color passed
        log.debug('color: %s', color)
        remove = ['remove', 'reset', 'rm', 'delete', 'del', 'none', 'default', 'false', 'no']
        if color.lower() in remove:
            removed = None
            for role in member.roles:
                if role.name.startswith(self.prefix):
                    removed = role
                    log.debug('Removing Role %s from Member %s', role.name, member.name)
                    await member.remove_roles(role, reason='Remove Color Role')
            if removed:
                msg = f'✅ Color Removed: {removed.name}. Use `/color HEX` to set.'
                return await ctx.send(msg, ephemeral=True, delete_after=120)
            else:
                msg = '⛔ No Color Roles Found. Use `/color HEX` to set.'
                return await ctx.send(msg, ephemeral=True, delete_after=30)

        # Validate color passed
        newcolor = self.color_converter(color)
        log.debug('newcolor: %s', newcolor)
        if not newcolor:
            return await ctx.send(self.error_message, ephemeral=True, delete_after=30)

        colorhex = newcolor.replace('0x', '')
        role_name = f'{self.prefix}{colorhex}'

        # Check if already has role, blocked_roles, and remove other roles
        blocked_roles = await self.config.guild(guild).blocked_roles()
        for role in member.roles:
            if role.name == role_name:
                # log.debug('User already has requested role: %s - %s', role.id, role.name)
                msg = f'⛔ Looks like you already have color role: {role.name}'
                await ctx.send(msg, ephemeral=True, delete_after=30)
                return
            if role.id in blocked_roles:
                msg = '⛔ You have a role that is blocked from color changes.'
                await ctx.send(msg, ephemeral=True, delete_after=30)
                return
            if role.name.startswith(self.prefix):
                log.debug('Removing Role %s from Member %s', role.name, member.name)
                await member.remove_roles(role, reason='Remove Color Role')

        # Get or create new color role
        log.debug('role_name: %s', role_name)
        role: discord.Role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            role: discord.Role = await guild.create_role(
                reason='Create Color Role',
                name=role_name,
                colour=discord.Colour(int(newcolor, 16)),
                permissions=discord.Permissions.none(),
            )
            log.debug('Created new role: %s - %s', role.id, role.name)

        # Add color role to user
        await member.add_roles(role, reason='Add Color Role')
        log.debug('Added Role %s to User %s', role.name, member.name)
        msg = f'✅ Color Updated: **{newcolor}**\n{self.color_info_url}{colorhex}'
        await ctx.send(msg, ephemeral=True, delete_after=120)

    @commands.group(name='colorme', aliases=['col'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def _colorme(self, ctx):
        """Manage the Color Command Options"""

    @_colorme.command(name='toggle', aliases=['enable', 'disable', 'on', 'off'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _colorme_toggle(self, ctx: commands.Context):
        """Enable/Disable Color Command"""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await self.config.guild(ctx.guild).enabled.set(False)
            return await ctx.send(f'✅ {self.__cog_name__} Disabled.', delete_after=120)
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(f'✅ {self.__cog_name__} Enabled.', delete_after=120)

    @_colorme.command(name='colorall', aliases=['all'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _colorme_colorall(self, ctx: commands.Context):
        """Color All Users with a Random Color"""
        enabled: bool = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await self.config.guild(ctx.guild).enabled.set(False)
            return await ctx.send(f'⛔ {self.__cog_name__} Disabled.', delete_after=120)
        await ctx.typing()
        blocked_roles: List[int] = await self.config.guild(ctx.guild).blocked_roles()
        needs_color: List[discord.Member] = []
        for member in ctx.guild.members:
            log.debug('%s - %s', member.id, member.name)
            if member.bot:
                log.debug('User %s is a bot', member.name)
                continue
            if member.color != discord.Color.default():
                log.debug('User %s has color %s', member.name, member.color)
                continue
            for role in member.roles:
                if role.id in blocked_roles:
                    log.debug('User %s has blocked role %s', member.name, role.name)
                    break
                if role.name.startswith(self.prefix):
                    log.debug('User %s has color role %s', member.name, role.name)
                    break
            else:
                needs_color.append(member)
                continue
            continue
        log.debug('needs_color: %s', [x.name for x in needs_color])
        if not needs_color:
            return await ctx.send('⛔ No members found that need color roles...', delete_after=120)
        # current_hexes: List[str] = []
        # log.debug('current_hexes: %s', current_hexes)
        # current_rgbs = [(1.0, 1.0, 1.0), (0.0, 0.0, 0.0)]
        # for hex_code in current_hexes:
        #     code = hex_code.lstrip('#').lower()
        #     rgb = tuple(int(code[i:i+2], 16) for i in (0, 2, 4))
        #     if rgb not in current_rgbs:
        #         current_rgbs.append(rgb)
        # log.debug('current_rgbs: %s', current_rgbs)
        # colors = distinctipy.get_colors(len(needs_color), exclude_colors=current_rgbs)
        colors = distinctipy.get_colors(len(needs_color))
        log.debug('colors: %s', colors)
        lines = [f'❔ Will apply the following {len(needs_color)} colors:\n```ini']
        member: discord.Member
        colors: Tuple[float, float, float]
        for member, color in zip(needs_color, colors):
            log.debug('%s - %s - %s', member.id, member.name, color)
            r, g, b = color
            colorhex = '%02x%02x%02x' % (int(r*255), int(g*255), int(b*255))
            line = f'[#{colorhex}]: @{member.name}'
            lines.append(line)
        lines.append('```')
        question = await ctx.send('\n'.join(lines), delete_after=120)
        start_adding_reactions(question, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(question, ctx.author)
        try:
            await self.bot.wait_for('reaction_add', check=pred, timeout=90)
        except asyncio.TimeoutError:
            return await ctx.send('⛔ Request has Timed Out...', delete_after=120)
        log.debug('pred.result: %s', pred.result)
        if pred.result is not True:
            return await ctx.send('⛔ Cancelled...', delete_after=120)
        msg = f'⌛ Processing {len(needs_color)} members with {len(colors)} colors.'
        process = await ctx.send(msg, delete_after=120)
        async with ctx.typing():
            async for member, color in AsyncIter(zip(needs_color, colors), delay=2, steps=10):
                guild: discord.Guild = member.guild
                r, g, b = color
                colorhex = '%02x%02x%02x' % (int(r*255), int(g*255), int(b*255))
                newcolor = f'0x{colorhex}'
                role_name = f'{self.prefix}{colorhex}'
                log.debug('role_name: %s', role_name)
                role: discord.Role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    role: discord.Role = await guild.create_role(
                        reason='Create Color Role',
                        name=role_name,
                        colour=discord.Colour(int(newcolor, 16)),
                        permissions=discord.Permissions.none(),
                    )
                    log.debug('Created new role: %s - %s', role.id, role.name)
                await member.add_roles(role, reason='Add Color Role')
                log.debug('Added Role %s to User %s', role.name, member.name)

        await question.delete()
        await process.delete()
        msg = f'✅ Done processing {len(needs_color)} members with {len(colors)} colors.'
        await ctx.send(msg, delete_after=120)

    @_colorme.command(name='uncolorall', aliases=['uncolor', 'removeall', 'deleteall'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _colorme_uncolorall(self, ctx: commands.Context):
        await ctx.typing()
        color_roles: List[discord.Role] = []
        role: discord.Role
        for role in ctx.guild.roles:
            if role.name.startswith(self.prefix):
                color_roles.append(role)
        if not color_roles:
            return await ctx.send('⛔ No Color Roles Found...', delete_after=120)
        lines = [x.mention for x in color_roles]
        content = '❔  Will **delete** the following roles; Proceed? ' + ' '.join(lines)
        question = await ctx.send(content, delete_after=120, allowed_mentions=discord.AllowedMentions.none())
        start_adding_reactions(question, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(question, ctx.author)
        try:
            await self.bot.wait_for('reaction_add', check=pred, timeout=90)
        except asyncio.TimeoutError:
            return await ctx.send('⛔ Request has Timed Out...', delete_after=120)
        log.debug('pred.result: %s', pred.result)
        if pred.result is not True:
            return await ctx.send('⛔ Cancelled...', delete_after=120)
        process = await ctx.send(f'⌛ Deleting {len(color_roles)} roles...', delete_after=120)
        async with ctx.typing():
            async for role in AsyncIter(color_roles, delay=3, steps=20):
                await role.delete()
        await process.delete()
        await ctx.send(f'✅ Done deleting {len(color_roles)} roles.', delete_after=120)

    # @colorme.command(name='set', aliases=['s'])
    # async def _colorme_set(self, ctx: commands.Context, user: discord.Member, color: Optional[str]):
    #     """Set a Color for a User"""
    #     # Copied from Color Command for quick manual setting of a users color
    #     guild = user.guild
    #
    #     # Check if color command is enabled in guild
    #     enabled = await self.config.guild(guild).enabled()
    #     if not enabled:
    #         msg = '⛔ Color Not Enabled in this Guild. Contact Server Manager to Enable.'
    #         await ctx.send(msg, ephemeral=True, delete_after=60)
    #         return
    #
    #     # Remove color if no color passed
    #     log.debug('color: %s', color)
    #     if not color:
    #         removed = None
    #         for role in user.roles:
    #             if role.name.startswith(self.prefix):
    #                 removed = role
    #                 log.debug('Removing Role %s from Member %s', role.name, user.name)
    #                 await user.remove_roles(role, reason='Remove Color Role')
    #         if removed:
    #             await ctx.send(f'✅ Color Removed: {removed.name}', ephemeral=True, delete_after=60)
    #         else:
    #             await ctx.send(f'⛔ No Color Roles Found.', ephemeral=True, delete_after=60)
    #         return
    #
    #     # Validate color passed
    #     newcolor = self.color_converter(color)
    #     log.debug('newcolor: %s', newcolor)
    #     if not newcolor:
    #         msg = (
    #             '⛔ Not a valid color code. Use a hex code like #990000, '
    #             'a Discord color name or a CSS3 color name.\n'
    #             '<https://discordpy.readthedocs.io/en/latest/api.html#colour>\n'
    #             '<https://www.w3.org/TR/2018/REC-css-color-3-20180619/#svg-color>'
    #         )
    #         await ctx.send(msg, ephemeral=True, delete_after=60)
    #         return
    #
    #     colorhex = newcolor.replace('0x', '')
    #     role_name = f'{self.prefix}{colorhex}'
    #
    #     # Check if already has role, blocked_roles, and remove other roles
    #     blocked_roles = await self.config.guild(guild).blocked_roles()
    #     for role in user.roles:
    #         if role.name == role_name:
    #             log.debug('User already has requested role: %s - %s', role.id, role.name)
    #             msg = f'⛔ Looks like you already have color role: {role.name}'
    #             await ctx.send(msg, ephemeral=True, delete_after=60)
    #             return
    #         if role.id in blocked_roles:
    #             msg = '⛔ You have a role that is protected from color changes.'
    #             await ctx.send(msg, ephemeral=True, delete_after=60)
    #             return
    #         if role.name.startswith(self.prefix):
    #             log.debug('Removing Role %s from Member %s', role.name, user.name)
    #             await user.remove_roles(role, reason='Remove Color Role')
    #
    #     # Get or create new color role
    #     log.debug('role_name: %s', role_name)
    #     role: discord.Role = discord.utils.get(guild.roles, name=role_name)
    #     if not role:
    #         role: discord.Role = await guild.create_role(
    #             reason='Custom Color Role',
    #             name=role_name,
    #             colour=discord.Colour(int(newcolor, 16)),
    #             permissions=discord.Permissions.none()
    #         )
    #         log.debug('Created new role: %s - %s', role.id, role.name)
    #
    #     # Add color role to user
    #     await user.add_roles(role)
    #     log.debug('Added Role: %s to User: %s', role.name, user.name)
    #     msg = f'✅ Color Updated: **{newcolor}**\n{self.color_info_url}{colorhex}'
    #     await ctx.send(msg, ephemeral=True, delete_after=60)

    # @colorme.command(name='block')
    # @checks.admin_or_permissions(manage_guild=True)
    # async def _colorme_block(self, ctx, role: discord.Role):
    #     """Add a role to the list of protected roles.
    #     Members with this role as top role will not be allowed to change color.
    #     Example: [p]colorme protect admin
    #     """
    #     blocked_roles = await self.config.guild(ctx.guild).blocked_roles()
    #     if role.id in blocked_roles:
    #         await ctx.send('⛔ That role is already protected.')
    #         return
    #     blocked_roles.append(role.id)
    #     await self.config.guild(ctx.guild).blocked_roles.set(blocked_roles)
    #     await ctx.send(f'✅ Users with top role {role} are blocked from color changes.')
    #
    # @colorme.command(name='unblock')
    # @checks.admin_or_permissions(manage_guild=True)
    # async def _colorme_unblock(self, ctx, role: discord.Role):
    #     """Remove a role from the list of blocked roles.
    #     Example: [p]colorme unprotect admin
    #     """
    #     blocked_roles = await self.config.guild(ctx.guild).blocked_roles()
    #     if role.id not in blocked_roles:
    #         await ctx.send('⛔ That role is not currently protected.')
    #         return
    #
    #     blocked_roles.remove(role.id)
    #     await self.config.guild(ctx.guild).blocked_roles.set(blocked_roles)
    #     await ctx.send(f'✅ Users with top role {role} are no longer protected from color changes.')
    #
    # @colorme.command(name='list')
    # async def _colorme_list(self, ctx):
    #     """Lists roles that are blocked from color changes."""
    #     guild = ctx.message.guild
    #     blocked_roles: list = await self.config.guild(guild).blocked_roles()
    #     msg_text = 'Protected role(s): '
    #     if len(blocked_roles) == 0:
    #         msg_text += 'None '
    #     for role in blocked_roles:
    #         protected_role: discord.Role = discord.utils.get(guild.roles, id=role)
    #         if protected_role is not None:
    #             msg_text += " '" + protected_role.name + "',"
    #     msg_text = msg_text[:-1] + '.'
    #     await ctx.send(msg_text)
