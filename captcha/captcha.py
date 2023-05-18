import asyncio
import discord
import json
import logging
import redis.asyncio as redis

from redbot.core import commands, Config

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
                await self.process_verification(message)
            await asyncio.sleep(0.01)

    async def process_verification(self, message):
        log.debug('raw_message: %s', message)
        data = json.loads(message['data'].decode('utf-8'))
        log.debug('data: %s', data)
        user_id = data['user']
        log.debug('user_id: %s', user_id)
        channel = data['channel']
        log.debug('channel: %s', channel)
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
        if enabled:
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
        role_name = f'`@{role.name}`' if role else '**NOT SET**'
        out = f'CAPTCHA Settings:\n' \
              f'Status: **{config["enabled"]}**\n' \
              f'Role: {role_name}\n' \
              f'Bots: {role_name}'
        await ctx.send(out)

