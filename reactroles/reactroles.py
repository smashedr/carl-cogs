import asyncio
import discord
import logging
import re
import emojis

from redbot.core import commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import MessagePredicate

logger = logging.getLogger('red.reactroles')


class Reactroles(commands.Cog):
    """Carl's Reactroles Cog"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(rr=None, at=None)

    async def initialize(self) -> None:
        logger.debug('Initializing Reactroles Cog')

    async def get_rr(self, guild, name):
        config = await self.config.guild(guild).rr() or {}
        config = config[name] if name in config else None
        return config

    async def put_rr(self, guild, name, data: dict):
        config = await self.config.guild(guild).rr() or {}
        config[name] = data
        await self.config.guild(guild).rr.set(config)

    async def get_at(self, guild, cm_id):
        config = await self.config.guild(guild).at() or {}
        config = config[cm_id] if cm_id in config else None
        return config

    async def put_at(self, guild, cm_id, data: str):
        config = await self.config.guild(guild).at() or {}
        config[cm_id] = data
        await self.config.guild(guild).at.set(config)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self.process_reaction(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self.process_reaction(payload)

    async def process_reaction(self, payload: discord.RawReactionActionEvent):
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            logger.debug('No guild')
            return
        if await self.bot.cog_disabled_in_guild(self, guild):
            logger.debug('Cog disabled in guild')
            return
        if payload.member and payload.member.bot:
            logger.debug('Bot')
            return
        if payload.member:
            member = payload.member
        else:
            member = guild.get_member(payload.user_id)
        if member.bot:
            logger.debug('Bot')
            return

        cm_id = f'{payload.channel_id}-{payload.message_id}'
        attach_name = await self.get_at(guild, cm_id)
        if not attach_name:
            logger.debug('NO attach_name')
            return
        logger.debug(attach_name)

        emoji_string = str(payload.emoji).strip("\N{VARIATION SELECTOR-16}")
        logger.debug(emoji_string)
        emoji = await self.verify_emoji(payload.emoji.id or emoji_string)
        logger.debug(emoji)

        rr = await self.get_rr(guild, attach_name)
        if not rr:
            logger.debug('NO role_id')
            return
        logger.debug(rr)
        if str(emoji) not in rr:
            logger.warning('React Role attached but non-matched emoji used.')
            return

        role_id = rr[str(emoji)]
        logger.debug(role_id)

        if role_id in [r.id for r in member.roles]:
            logger.info('Removing Role')
            role = guild.get_role(int(role_id))
            await member.remove_roles(role)
        else:
            logger.info('Adding Role')
            role = guild.get_role(int(role_id))
            await member.add_roles(role)

    async def verify_emoji(self, emoji_input: str, encode=False):
        # logger.debug('emoji_input: %s', emoji_input)
        if isinstance(emoji_input, discord.Emoji):
            return emoji_input
        if isinstance(emoji_input, str):
            if encode:
                if emojis.count(emojis.encode(emoji_input)) > 0:
                    return emojis.encode(emoji_input)
            else:
                if emojis.count(emoji_input) > 0:
                    logger.debug('emojis.count > 0')
                    return emojis.decode(emoji_input)
                if emojis.count(emojis.encode(emoji_input)) > 0:
                    logger.debug('emojis.encode emojis.count > 0')
                    return emojis.decode(emoji_input)

            re_find = re.findall(r'\d{18}', emoji_input)
            if not re_find:
                return None

            emoji_id = int(re_find[0])
        elif isinstance(emoji_input, int):
            emoji_id = emoji_input
        else:
            return None
        emoji = discord.utils.get(self.bot.emojis, id=emoji_id)
        return emoji

    @commands.group(name='reactroles', aliases=['reactrole', 'rr'])
    @commands.guild_only()
    @commands.admin()
    async def reactroles(self, ctx):
        """Manage React Roles and the messages their attached too."""

    @reactroles.command(name='create', aliases=["c"])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def create(self, ctx, *, name: str):
        """
        Create a Reaction Role set.
        `<name>` A unique name for the reaction role.
        """
        name = name.lower()
        rr = await self.get_rr(ctx.guild, name)
        if rr:
            await ctx.send(f'React Role "{name}" already exists, editing it.')
            await self.edit_rr(ctx, name)  # edit rr
            return
        await ctx.send(f'Creating React Role "{name}" and editing it.')
        await self.edit_rr(ctx, name)  # edit rr
        return

    async def edit_rr(self, ctx, name):
        msg = f'Now updating React Role **{name}**\nPlease enter one set of ' \
              '`emoji` `role name` pairs per line and in the order you want ' \
              'them to appear. Example: \n:red_square: ' \
              'Red Role\nWhen finished adding all emoji/role pairs type ' \
              '`done` or to abort type `cancel` the request. '
        org_msg = await ctx.send(msg)
        init_msg = await ctx.send('Emoji/Role pairs will show up here:')
        roles = {}
        pred = MessagePredicate.same_context(ctx)
        while True:
            try:
                message = await self.bot.wait_for("message", check=pred, timeout=30)
            except asyncio.TimeoutError:
                await ctx.send(f'Request timed out. You need to start over.')
                await org_msg.delete()
                await init_msg.delete()
                return

            if message.content.lower().strip() in ['abort', 'cancel', 'stop']:
                logger.debug('abort')
                await org_msg.delete()
                await init_msg.delete()
                await message.delete()
                break
            if message.content.lower().strip() in ['done', 'complete']:
                logger.debug('done')
                await message.delete()
                break

            resp = message.content.split(' ')
            if len(resp) < 2:
                await ctx.send('Not enough input.', delete_after=5)
                await message.delete()
                continue

            emoji_name = resp.pop(0)
            role_name = ' '.join(resp).strip()
            # logger.debug('"%s"', emoji_name.encode('unicode_escape'))

            emoji = await self.verify_emoji(emoji_name)
            if not emoji:
                await ctx.send('Invalid emoji in input.', delete_after=5)
                await message.delete()
                continue
            logger.debug(emoji)
            logger.debug(str(emoji))

            # role = ctx.guild.get_role(name=role_name)
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if not role:
                await ctx.send('Invalid role in input. Roles are **case sensitive**.', delete_after=5)
                await message.delete()
                continue
            if role >= ctx.guild.me.top_role:
                await ctx.send(f"Can not give out `@{role}` because it is higher "
                               f"than all the bot's current roles. ", delete_after=10)
                continue
            logger.debug(role)

            if str(emoji) not in roles:
                roles.update({str(emoji): role.id})
                update = init_msg.content + f'\n{emoji} - `@{role.name}`'
                await init_msg.edit(content=update)
                await message.delete()
                logger.info(roles)
            else:
                await ctx.send('Already added emoji.', delete_after=5)

        logger.debug('name: %s', name)
        await self.put_rr(ctx.guild, name, roles)
        await ctx.send('React Role Creation Finished. You may now attach this '
                       'role to a message with the [p]rr attach command.')

    @reactroles.command(name='attach', aliases=["a"])
    async def attach(self, ctx, message: discord.Message, *, name: str):
        """
        Create a reaction role
        `<message>` The channel_id-message_id pair. Right click on the message,
        hold SHIFT, then click Copy ID. If you don't see Copy ID enable it under
        User Settings -> Advanced -> Developer Mode
        `<name>` The name of a previouly created Reaction Role.
        """
        logger.debug(message.channel.id)
        logger.debug(message.id)
        logger.debug(name)
        if not message.guild or message.guild.id != ctx.guild.id:
            await ctx.send('Can not add a Reaction Role to a message not in this guild.')
            return

        rr = await self.get_rr(ctx.guild, name.lower())
        if not rr:
            await ctx.send(f'React Role {name} was not found.')
            return
        logger.debug(rr)

        raw_emoji_list = list(rr.keys())
        emoji_list = []
        for emoji in raw_emoji_list:
            e = await self.verify_emoji(emoji, encode=True)
            emoji_list.append(e)
        logger.debug(emoji_list)

        await message.clear_reactions()
        await start_adding_reactions(message, emoji_list)
        cm_id = f'{message.channel.id}-{message.id}'
        await self.put_at(ctx.guild, cm_id, name.lower())
        await ctx.send('Success!')

    # @reactroles.command(name='create', aliases=["c"])
    # async def create(self, ctx, emoji: discord.Emoji, role: discord.Role):
    #     """
    #     Create a reaction role set.
    #     `<emoji>` The emoji you want people to react with.
    #     `<role>` The role you want people to receive.
    #     """
    #     logger.debug(emoji)
    #     logger.debug(role)
    #     # if not message.guild or message.guild.id != ctx.guild.id:
    #     #     await ctx.send(_("You cannot add a Reaction Role to a message not in this guild."))
    #     #     return
    #     # async with self.config.guild(ctx.guild).reaction_roles() as cur_setting:
    #     #     if isinstance(emoji, discord.Emoji):
    #     #         use_emoji = str(emoji.id)
    #     #     else:
    #     #         use_emoji = str(emoji).strip("\N{VARIATION SELECTOR-16}")
    #     await ctx.send('yep')
