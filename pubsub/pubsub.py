import asyncio
import json
import logging
import redis.asyncio as redis
from typing import Optional, Iterable, List

from redbot.core import commands

log = logging.getLogger('red.pubsub')


class Pubsub(commands.Cog):
    """Carl's Pubsub Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.loop: Optional[asyncio.Task] = None
        self.client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data = await self.bot.get_shared_api_tokens('redis')
        self.client = redis.Redis(
            host=data['host'] if 'host' in data else 'redis',
            port=int(data['port']) if 'port' in data else 6379,
            db=int(data['db']) if 'db' in data else 0,
            password=data['pass'] if 'pass' in data else None,
        )
        await self.client.ping()
        self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        self.loop = asyncio.create_task(self.pubsub_loop())
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        if self.loop and not self.loop.cancelled():
            log.info('Stopping Loop')
            self.loop.cancel()

    async def pubsub_loop(self):
        log.info('%s: Start Main Loop', self.__cog_name__)
        await self.pubsub.subscribe('red.pubsub')
        while self is self.bot.get_cog('Pubsub'):
            log.info('pubsub_loop:while')
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

            log.debug('data.requests: %s', data['requests'])
            resp = dict()
            if 'roles' in data['requests']:
                resp['roles'] = self.process_roles(guild.roles)
            if 'channels' in data['requests']:
                resp['channels'] = self.process_channels(guild.channels)
            if 'members' in data['requests']:
                resp['members'] = self.process_members(guild.members)
            if 'guild' in data['requests']:
                resp['guild'] = self.process_guild(guild)
            log.debug('resp: %s', resp)
            response = json.dumps(resp, default=str)
            pr = await self.client.publish(channel, response)
            log.debug('pr: %s', pr)
        except Exception as error:
            log.error('Exception processing message.')
            log.exception(error)
            # resp = {'success': False, 'message': str(error)}

    @staticmethod
    def process_guild(guild) -> dict:
        log.debug('process_guild: %s', guild.id)
        data = {
            'id': guild.id,
            'banner': guild.banner,
            'default_role': guild.default_role,
            'description': guild.description,
            'icon': guild.icon,
            'member_count': guild.member_count,
            'name': guild.name,
            'owner_id': guild.owner_id,
        }
        return data

    @staticmethod
    def process_roles(roles) -> list:
        log.debug('process_roles')
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
    def process_channels(channels) -> list:
        log.debug('process_channels')
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
    def process_members(cls, members) -> list:
        log.debug('process_members')
        resp = []
        for member in members:
            data = {
                'id': member.id,
                'name': member.name,
                'discriminator': member.discriminator,
                'nick': member.nick,
                'display_name': member.display_name,
                'default_avatar': member.default_avatar,
                'avatar': member.avatar,
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
    def process_iterable(iterable: Iterable, keys: List) -> List:
        resp = []
        for i in iterable:
            data = {}
            for key in keys:
                data[key] = getattr(i, key)
            resp.append(data)
        return resp
