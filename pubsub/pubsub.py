import aredis
import asyncio
import json
import logging
import time
from redbot.core import commands

logger = logging.getLogger('red.pubsub')


class PubSub(commands.Cog):
    """My PubSub Cog"""

    def __init__(self, bot):
        logger.debug("__init__")
        self.bot = bot
        self.loop = None
        self.client = None
        self.pubsub = None

    @staticmethod
    def my_handler(x):
        print(x)

    async def initialize(self):
        """
        This does NOT work, please tell me why!
        """
        logger.debug("Initializing PubSub Cog Start")
        # await self.bot.wait_until_ready()
        logger.debug('bot.wait_until_ready')
        self.client = aredis.StrictRedis(host='redis', port=6379, db=0)
        self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        self.loop = asyncio.create_task(self.my_main_loop())
        logger.debug("Initializing PubSub Cog Finished")

    async def my_main_loop(self) -> None:
        logger.debug('my_main_loop')
        # await pubsub.subscribe(**{'my-channel': self.my_handler}, ignore_subscribe_messages=True)
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
            print(data)
            await self.client.publish(channel, json.dumps(data))
        except Exception as error:
            logger.exception(error)
            logger.warning('Exception processing message.')

    @staticmethod
    def process_roles(roles):
        resp = []
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
            resp.append(data)
        return resp

    @staticmethod
    def process_channels(channels):
        resp = []
        for channel in channels:
            data = {
                'type': channel.type,
                'position': channel.position,
                'id': channel.id,
                'name': channel.name,
            }
            resp.append(data)
        return resp

    # @staticmethod
    # def process_iterable(iterable):
    #     keys = ['color', 'hoist', 'id', 'managed', 'mentionable', 'name', 'permissions', 'position', 'tags']
    #     resp = []
    #     for i in iterable:
    #         data = {}
    #         for key in keys:
    #             data[key] = getattr(i, key)
    #         resp.append(data)
    #     return resp
