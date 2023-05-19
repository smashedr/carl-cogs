import asyncio
import discord
import json
import logging
import redis.asyncio as redis

from redbot.core import commands, Config
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

log = logging.getLogger('red.captcha')


class Captcha(commands.Cog):
    """
    Carl's CAPTCHA Cog.
        [p]set api
        Name: redis
        Data:
        host    hostname
        port    portnumber
        db      dbnumber
        pass    password
    """

    guild_default = {
        'enabled': False,
        'role': None,
        'bots': True,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        self.loop = None
        self.client = None
        self.pubsub = None

    async def cog_load(self):
        log.info(f'{self.__cog_name__}: Cog Load Start')
        data = await self.bot.get_shared_api_tokens('redis')
        self.client = redis.Redis(
            host=data['host'] if 'host' in data else 'redis',
            port=int(data['port']) if 'port' in data else 6379,
            db=int(data['db']) if 'db' in data else 0,
            password=data['pass'] if 'pass' in data else None,
        )
        self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        self.loop = asyncio.create_task(self.captcha_loop())
        log.info(f'{self.__cog_name__}: Cog Load Finish')

    async def cog_unload(self):
        log.info(f'{self.__cog_name__}: Cog Unload')
        self.loop.cancel()

    async def captcha_loop(self) -> None:
        log.info(f'{self.__cog_name__}: Start Main Loop')
        await self.pubsub.subscribe('red.captcha')
        while self is self.bot.get_cog('Captcha'):
            log.info('captcha_loop:while')
            message = await self.pubsub.get_message(timeout=None)
            if message:
                await self.process_message(message)
            await asyncio.sleep(0.01)

    async def process_message(self, message: dict) -> None:
        try:
            log.debug('message: %s', message)
            data = json.loads(message['data'].decode('utf-8'))
            log.debug('data: %s', data)

            channel = data['channel']
            log.debug('channel: %s', channel)

            guild = self.bot.get_guild(int(data['guild']))
            log.debug('guild: %s', guild)

            user_id = data['user']
            log.debug('user_id: %s', user_id)
            member = await guild.fetch_member(int(user_id))

            log.debug('data.requests: %s', data['requests'])
            resp = dict()
            if 'data' in data['requests']:
                resp = await self.process_get_data(guild, member, data)
            if 'verify' in data['requests']:
                resp = await self.process_verification(guild, member, data)
            log.debug('resp: %s', resp)
            pr = await self.client.publish(channel, json.dumps(resp, default=str))
            log.debug('pr: %s', pr)
        except Exception as error:
            log.exception(error)
            log.warning('Exception processing message.')

    @classmethod
    async def process_get_data(cls, guild: discord.Guild, member: discord.Member,
                         data: dict) -> dict:
        log.debug('process_members')
        member_data = {
            'id': member.id,
            'name': member.name,
            'discriminator': member.discriminator,
            'nick': member.nick,
            'display_name': member.display_name,
            'default_avatar': str(member.default_avatar),
            'avatar': str(member.avatar),
            # 'roles': cls.process_iterable(member.roles, ['id', 'name']),
            'bot': bool(member.bot),
            'pending': bool(member.pending),
            'status': member.status,
            'color': member.color,
            'joined_at': member.joined_at,
        }
        guild_data = {
            'id': guild.id,
            'banner': guild.banner,
            'default_role': guild.default_role,
            'description': guild.description,
            'icon': guild.icon,
            'member_count': guild.member_count,
            'name': guild.name,
            'owner_id': guild.owner_id,
        }
        return {'member': member_data, 'guild': guild_data}

    async def process_verification(self, guild: discord.Guild,
                                   member: discord.Member,
                                   data: dict) -> dict:
        # log.debug('message: %s', message)
        # data = json.loads(message['data'].decode('utf-8'))
        log.debug('data: %s', data)
        channel = data['channel']
        log.debug('channel: %s', channel)

        log.debug('member.id: %s', member.id)
        log.debug('guild.id: %s', guild.id)

        config = await self.config.guild(guild).all()
        if not config['enabled']:
            response = json.dumps({'success': False, 'message': 'Disabled'})
        else:
            role = guild.get_role(int(config['role']))
            await member.add_roles(role)
            response = json.dumps({'success': True})

        log.debug('response: %s', response)
        await self.client.publish(channel, response)

    # @commands.Cog.listener(name='on_message_without_command')
    # async def on_message_without_command(self, message: discord.Message) -> None:
    #     """Listens for messages."""
    #     if not message or not message.guild:
    #         return
    #
    #     conf = await self.config.guild(message.guild).all()
    #     if not conf['enabled']:
    #         return
    #
    #     if message.author.bot:
    #         if not conf['bots']:
    #             return
    #
    #     if conf['role'] in message.author.roles:
    #         return
    #
    #     # User needs CAPTCHA verification - Need Web API
    #     channel = await message.author.create_dm()
    #     await channel.send('CAPTCHA Verification Required.')

    @commands.group(name='captcha', aliases=['cap'])
    @commands.guild_only()
    @commands.admin()
    async def captcha(self, ctx):
        """Options for manging CAPTCHA."""

    @captcha.command(name='role', aliases=['r'])
    async def captcha_channel(self, ctx, *, role: discord.Role):
        """Sets the CAPTCHA Role."""
        await self.config.guild(ctx.guild).role.set(role.id)
        await ctx.send(f'✅ CAPTCHA role set to: `@{role.name}`')

    @captcha.command(name='enable', aliases=['e', 'on'])
    async def captcha_enable(self, ctx):
        """Enables CAPTCHA."""
        role = await self.config.guild(ctx.guild).role()
        enabled = await self.config.guild(ctx.guild).enabled()
        if not role:
            await ctx.send('⛔ CAPTCHA role not set. Please set first.')
        elif enabled:
            await ctx.send('✅ CAPTCHA module already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('✅ CAPTCHA module enabled.')

    @captcha.command(name='disable', aliases=['d', 'off'])
    async def captcha_disable(self, ctx):
        """Disable CAPTCHA."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('✅ CAPTCHA module already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('✅ CAPTCHA module disabled.')

    @captcha.command(name='status', aliases=['s', 'settings'])
    async def captcha_status(self, ctx):
        """Get CAPTCHA status."""
        config = await self.config.guild(ctx.guild).all()
        role = ctx.guild.get_role(config['role'])
        role_name = f'`@{role.name}`' if role else '⛔ **Not Set**'
        out = f'CAPTCHA Settings:\n' \
              f'Enabled: **{config["enabled"]}**\n' \
              f'Role: {role_name}\n' \
              f'Bots: {config["bots"]}'
        await ctx.send(out)

    @captcha.command(name='setup', aliases=['auto', 'a'])
    async def userchannels_setup(self, ctx):
        """AUTO Setup of CAPTCHA module."""
        guild = ctx.guild
        message = await ctx.send('This will automatically setup CAPTCHA by '
                                 'removing most permissions from `@everyone` '
                                 'and adding a `verified` role with the '
                                 'current permissions of `@everyone`.\n'
                                 'Proceed?')
        pred = ReactionPredicate.yes_or_no(message, ctx.author)
        start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            await self.bot.wait_for('reaction_add', check=pred, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send('⛔ Request timed out. Aborting.', delete_after=5)
            await message.delete()
            return

        if not pred.result:
            await ctx.send('⛔ Aborting.', delete_after=5)
            await message.delete()
            return

        await ctx.typing()
        await message.clear_reactions()
        await message.edit(content='⌛ Starting CAPTCHA Setup...')

        config = await self.config.guild(ctx.guild).all()
        log.debug(config)

        everyone = guild.get_role(guild.id)
        log.debug(everyone.permissions)
        await message.edit(content='⌛ Creating role `Verified`.')
        role = await guild.create_role(
            name='Verified',
            permissions=everyone.permissions,
        )

        await message.edit(content='⌛ Adding `Verified` role to all Members.')
        await ctx.typing()
        for member in guild.members:
            log.debug('member: %s', member)
            await member.add_roles(role)

        await ctx.typing()
        await message.edit(content='⌛ Updating `@everyone` permissions.')
        # Remove @everyone permissions
        await everyone.edit(permissions=discord.Permissions.none())
        # Update the permissions of the 'everyone' role
        perms = discord.Permissions(
            connect=True,
            change_nickname=True,
            read_message_history=True,
            view_channel=True,
        )
        await everyone.edit(permissions=perms)

        await message.edit(content='⌛ Updating CAPTCHA settings.')
        await self.config.guild(ctx.guild).enabled.set(True)
        await self.config.guild(ctx.guild).role.set(role.id)

        await message.edit(content='✅ All Done!')
