import asyncio
import discord
import logging
import redis.asyncio as redis

from redbot.core import commands, Config

log = logging.getLogger('red.captcha')


class Captcha(commands.Cog):
    """Carl's Server CAPTCHA Cog."""

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

    async def captcha_loop(self) -> None:
        log.info(f'{self.__cog_name__}: Start Main Loop')
        await self.pubsub.subscribe('red.captcha')
        while self is self.bot.get_cog('Captcha'):
            # log.info('captcha_loop:while')
            # message = await self.wait_for_message(self.pubsub)
            message = await self.pubsub.get_message(timeout=1)
            if message:
                await self.process_verification(message)
            await asyncio.sleep(0.01)

    async def process_verification(self, message):
        log.debug('message: %s', message)
        return None

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message) -> None:
        """Listens for messages."""
        if not message or not message.guild:
            return

        conf = await self.config.guild(message.guild).all()
        if not conf['enabled']:
            return

        if message.author.bot:
            if not conf['bots']:
                return

        if conf['role'] in message.author.roles:
            return

        # User needs CAPTCHA verification - Need Web API
        channel = await message.author.create_dm()
        await channel.send('CAPTCHA Verification Required.')

    @commands.group(name='captcha', aliases=['cap'])
    @commands.guild_only()
    @commands.admin()
    async def captcha(self, ctx):
        """Options for managing CAPTCHA."""

    @captcha.command(name='enable', aliases=['on'])
    async def captcha_enable(self, ctx):
        """Enables CAPTCHA."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('CAPTCHA is already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('CAPTCHA has been enabled.')

    @captcha.command(name='disable', aliases=['off'])
    async def captcha_disable(self, ctx):
        """Disable CAPTCHA."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('CAPTCHA is already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('CAPTCHA has been disabled.')

    @captcha.command(name='set')
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def captcha_add(self, ctx, *, role: discord.Role):
        """Set CAPTCHA Passed Role."""
        roles = await self.config.guild(ctx.guild).roles() or []
        log.debug(roles)
        if role.id not in roles:
            if role >= ctx.guild.me.top_role:
                await ctx.send(f"Can not give out `@{role}` because it is "
                               f"higher than all the bot's current roles. ")
                return
            roles.append(role.id)
            await self.config.guild(ctx.guild).roles.set(roles)
            await ctx.send(f'Now giving members the role `@{role}`')
        else:
            await ctx.send(f'Already giving new members the role `@{role}`')

        if not await self.config.guild(ctx.guild).enabled():
            await ctx.send('**Warning:** CAPTCHA is **DISABLED**. Enable it.')

    @captcha.command(name='status', aliases=['info', 'settings'])
    async def captcha_status(self, ctx):
        """Get CAPTCHA status."""
        config = await self.config.guild(ctx.guild).all()
        log.debug(config)
        status = '**Enabled**' if config['enabled'] else '**NOT ENABLED**'
        if not config['role']:
            await ctx.send(f'CAPTCHA Role NOT Set...')
            return
        out = [f'Status: **{status}**\nRole:   **{config["role"]}**']
        await ctx.send(''.join(out))

