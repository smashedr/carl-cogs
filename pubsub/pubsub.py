import asyncio
import json
import logging
import time
import redis.asyncio as redis

from redbot.core import commands, Config
# from redbot.core.utils.predicates import MessagePredicate

log = logging.getLogger('red.pubsub')


class Pubsub(commands.Cog):
    """Carl's Pubsub Cog"""

    def __init__(self, bot):
        self.bot = bot
        # self.config = Config.get_conf(self, 1337, True)
        # self.config.register_global(host='redis', password=None)
        self.loop = None
        self.client = None
        self.pubsub = None

    async def cog_load(self) -> None:
        log.info(f'{self.__cog_name__}: Cog Load Start')
        data = await self.bot.get_shared_api_tokens('redis')
        self.client = redis.Redis(
            host=data['host'] if 'host' in data else 'redis',
            port=int(data['port']) if 'port' in data else 6379,
            db=int(data['db']) if 'db' in data else 0,
            password=data['pass'] if 'pass' in data else None,
        )
        self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        self.loop = asyncio.create_task(self.pubsub_loop())
        log.info(f'{self.__cog_name__}: Cog Load Finished')

    async def cog_unload(self) -> None:
        log.info(f'{self.__cog_name__}: Cog Unload')
        self.loop.cancel()

    async def pubsub_loop(self) -> None:
        log.info(f'{self.__cog_name__}: Start Main Loop')
        await self.pubsub.subscribe('red.pubsub')
        while self is self.bot.get_cog('Pubsub'):
            # log.info('pubsub_loop:while')
            message = await self.pubsub.get_message(timeout=1)
            if message:
                await self.process_message(message)
            await asyncio.sleep(0.01)

    async def process_message(self, raw_message):
        try:
            log.debug('raw_message: %s', raw_message)
            message = json.loads(raw_message['data'].decode('utf-8'))
            log.debug('message: %s', message)
            channel = message['channel']
            log.debug('channel: %s', channel)
            guild = self.bot.get_guild(message['guild'])
            log.debug('guild: %s', guild)
            data = dict()
            if 'roles' in message['requests']:
                data['roles'] = self.process_roles(guild.roles)
            if 'channels' in message['requests']:
                data['channels'] = self.process_channels(guild.channels)
            if 'members' in message['requests']:
                data['members'] = self.process_members(guild.members)
            if 'guild' in message['requests']:
                data['guild'] = self.process_guild(guild)
            if 'verify' in message['requests']:
                data['verify'] = await self.process_verify(guild, message)
            # log.debug(data)
            await self.client.publish(channel, json.dumps(data, default=str))
        except Exception as error:
            log.exception(error)
            log.warning('Exception processing message.')

    async def process_verify(self, guild, message):
        log.debug('process_verify: %s', guild.id)
        user_id = message["data"]["user"]
        log.debug('user_id: %s', user_id)
        log.debug(message)
        # await self.client.setex(f'verify:{user_id}', 300, 1)
        p = await self.client.publish('red.captcha', f'{user_id}')
        log.debug('p: %s', p)
        data = {'is_success': True, 'message': 'success'}
        return data

    @staticmethod
    def process_guild(guild):
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
    def process_iterable(iterable, keys: list) -> list:
        resp = []
        for i in iterable:
            data = {}
            for key in keys:
                data[key] = getattr(i, key)
            resp.append(data)
        return resp

    # @commands.group(name='pubsub', aliases=['ps'])
    # @commands.is_owner()
    # async def pubsub(self, ctx):
    #     """Options for configuring Pubsub."""
    #
    # @pubsub.command(name='start', aliases=['on'])
    # async def pubsub_start(self, ctx):
    #     """Starts Pubsub."""
    #     # enabled = await self.config.enabled()
    #     await ctx.send(f'Pubsub started. Does not work. '
    #                    f'`{ctx.prefix}load pubsub` instead.')
    #
    # @pubsub.command(name='stop', aliases=['off'])
    # async def pubsub_stop(self, ctx):
    #     """Stops Pubsub."""
    #     # enabled = await self.config.enabled()
    #     await ctx.send(f'Pubsub stopped. Does not work. '
    #                    f'`{ctx.prefix}unload pubsub` instead.')
    #
    # @pubsub.command(name='set', aliases=['s'])
    # async def pubsub_set(self, ctx, setting):
    #     """Set optional Pubsub settings."""
    #     # enabled = await self.config.enabled()
    #     if setting.lower() in ['password', 'pass']:
    #         await ctx.send('Check your DM.')
    #         channel = await ctx.author.create_dm()
    #         await channel.send('Please enter the password...')
    #         pred = MessagePredicate.same_context(channel=channel, user=ctx.author)
    #         try:
    #             response = await self.bot.wait_for("message", check=pred, timeout=30)
    #         except asyncio.TimeoutError:
    #             await channel.send(f'Request timed out. You need to start over.')
    #             return
    #         if response:
    #             password = response.content
    #             await channel.send('Password recorded successfully. You can delete '
    #                                'the message containing the password now!')
    #         else:
    #             log.debug('Error like wtf yo...')
    #             log.debug(pred.result)
    #             log.debug(response.content)
    #             return
    #         log.debug('SUCCESS password')
    #         if password == 'none':
    #             password = None
    #         log.debug(password)
    #         await self.config.password.set(password)
    #
    #     elif setting.lower() in ['hostname', 'host']:
    #         await ctx.channel.send('Please enter the hostname...')
    #         pred = MessagePredicate.same_context(ctx)
    #         try:
    #             response = await self.bot.wait_for("message", check=pred, timeout=30)
    #         except asyncio.TimeoutError:
    #             await ctx.channel.send(f'Request timed out. You need to start over.')
    #             return
    #         if response:
    #             host = response.content
    #             await ctx.channel.send('Hostname recorded successfully.')
    #         else:
    #             log.debug('Error like wtf yo...')
    #             log.debug(pred.result)
    #             log.debug(response.content)
    #             return
    #         log.debug('SUCCESS hostname')
    #         log.debug(host)
    #         await self.config.host.set(host)
