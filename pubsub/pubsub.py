import aredis
import asyncio
import json
import logging
import time
from redbot.core import commands, Config
from redbot.core.utils.predicates import MessagePredicate

logger = logging.getLogger('red.pubsub')


class PubSub(commands.Cog):
    """Carl's PubSub Cog"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(host='redis', password=None)
        self.loop = None
        self.client = None
        self.pubsub = None
        self.host = None
        self.password = None

    def cog_unload(self):
        self.loop.cancel()

    async def initialize(self):
        logger.debug("Initializing PubSub Cog Start")
        self.host = await self.config.host()
        self.password = await self.config.password()
        logger.debug(self.host)
        logger.debug(self.password)
        self.client = aredis.StrictRedis(host=self.host, port=6379, db=0, password=self.password)
        self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        self.loop = asyncio.create_task(self.my_main_loop())
        logger.debug("Initializing PubSub Cog Finished")

    async def my_main_loop(self) -> None:
        logger.debug('my_main_loop')
        await self.pubsub.subscribe('loop')
        while self is self.bot.get_cog('PubSub'):
            # logger.debug('looping: my_main_loop')
            message = await self.wait_for_message(self.pubsub)
            if message:
                await self.process_message(message)
            await asyncio.sleep(0.01)

    async def wait_for_message(self, pubsub, timeout=3):
        # logger.debug('wait_for_message:timeout=1')
        now = time.time()
        timeout = now + timeout
        while now < timeout:
            message = await pubsub.get_message(timeout=1)
            if message is not None:
                return message
            await asyncio.sleep(0.01)
            now = time.time()
        return None

    async def process_message(self, raw_message):
        try:
            message = json.loads(raw_message['data'].decode('utf-8'))
            logger.debug('message: %s', message)
            channel = message['channel']
            logger.debug('channel: %s', channel)
            guild = self.bot.get_guild(message['guild'])
            data = {}
            if 'roles' in message['requests']:
                data['roles'] = self.process_roles(guild.roles)
            if 'channels' in message['requests']:
                data['channels'] = self.process_channels(guild.channels)
            if 'members' in message['requests']:
                data['members'] = self.process_members(guild.members)
            logger.debug(data)
            await self.client.publish(channel, json.dumps(data, default=str))
        except Exception as error:
            logger.exception(error)
            logger.warning('Exception processing message.')

    @staticmethod
    def process_roles(roles):
        response = []
        for role in roles:
            data = {
                'color': str(role.color),
                'hoist': role.hoist,
                'id': role.id,
                'managed': role.managed,
                'mentionable': role.mentionable,
                'name': role.name,
                'permissions': role.permissions.value,
                'position': role.position,
            }
            response.append(data)
        return response

    @staticmethod
    def process_channels(channels):
        response = []
        for channel in channels:
            data = {
                'type': channel.type,
                'position': channel.position,
                'id': channel.id,
                'name': channel.name,
            }
            response.append(data)
        return response

    @classmethod
    def process_members(cls, members):
        resp = []
        for member in members:
            data = {
                'id': member.id,
                'name': member.name,
                'discriminator': member.discriminator,
                'nick': member.nick,
                'display_name': member.display_name,
                'default_avatar_url': member.default_avatar_url,
                'avatar_url': member.avatar_url,
                'roles': cls.process_iterable(member.roles, ['id', 'name']),
                'bot': bool(member.bot),
                'pending': bool(member.pending),
                'status': member.status,
                'color': member.color,
                'joined_at': member.joined_at,
            }
            resp.append(data)
        return resp

    @staticmethod
    def process_iterable(iterable, keys: list) -> list:
        resp = []
        for i in iterable:
            data = {}
            for key in keys:
                data[key] = getattr(i, key)
            resp.append(data)
        return resp

    @commands.group(name='pubsub', aliases=['ps'])
    @commands.is_owner()
    async def pubsub(self, ctx):
        """Options for configuring PubSub."""

    @pubsub.command(name='start', aliases=['on'])
    async def pubsub_start(self, ctx):
        """Starts PubSub."""
        # enabled = await self.config.enabled()
        await ctx.send('PubSub started. Does not work.')

    @pubsub.command(name='stop', aliases=['off'])
    async def pubsub_stop(self, ctx):
        """Stops PubSub."""
        # enabled = await self.config.enabled()
        await ctx.send('PubSub stopped. Does not work, [p]unload instead.')

    @pubsub.command(name='set', aliases=['s'])
    async def pubsub_set(self, ctx, setting):
        """Set optional PubSub settings."""
        # enabled = await self.config.enabled()
        if setting.lower() in ['password', 'pass']:
            await ctx.send('Check your DM.')
            channel = await ctx.author.create_dm()
            await channel.send('Please enter the password...')
            pred = MessagePredicate.same_context(channel=channel, user=ctx.author)
            try:
                response = await self.bot.wait_for("message", check=pred, timeout=30)
            except asyncio.TimeoutError:
                await channel.send(f'Request timed out. You need to start over.')
                return
            if response:
                password = response.content
                await channel.send('Password recorded successfully. You can delete '
                                   'the message containing the password now!')
            else:
                logger.debug('Error like wtf yo...')
                logger.debug(pred.result)
                logger.debug(response.content)
                return
            logger.debug('SUCCESS password')
            logger.debug(password)
            await self.config.password.set(password)

        elif setting.lower() in ['hostname', 'host']:
            await ctx.channel.send('Please enter the hostname...')
            pred = MessagePredicate.same_context(ctx)
            try:
                response = await self.bot.wait_for("message", check=pred, timeout=30)
            except asyncio.TimeoutError:
                await ctx.channel.send(f'Request timed out. You need to start over.')
                return
            if response:
                host = response.content
                await ctx.channel.send('Hostname recorded successfully.')
            else:
                logger.debug('Error like wtf yo...')
                logger.debug(pred.result)
                logger.debug(response.content)
                return
            logger.debug('SUCCESS hostname')
            logger.debug(host)
            await self.config.host.set(host)
