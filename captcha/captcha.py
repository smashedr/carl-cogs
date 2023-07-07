import asyncio
import discord
import json
import logging
import redis.asyncio as redis
from typing import Optional

from redbot.core import commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from .menus import VerifyView

log = logging.getLogger('red.captcha')


class Captcha(commands.Cog):
    """Carl's CAPTCHA Cog"""

    guild_default = {
        'enabled': False,
        'verified': 0,
        'bots': True,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        self.loop: Optional[asyncio.Task] = None
        self.redis: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.url: Optional[str] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        self.bot.add_view(VerifyView(self))
        captcha = await self.bot.get_shared_api_tokens('captcha')
        if 'url' in captcha and captcha['url']:
            self.url = captcha['url'].replace('/verify', '').strip('/')
        if not self.url:
            log.warning('CAPTCHA API URL NOT SET!!!')
        redis_data: dict = await self.bot.get_shared_api_tokens('redis')
        self.redis = redis.Redis(
            host=redis_data.get('host', 'redis'),
            port=int(redis_data.get('port', 6379)),
            db=int(redis_data.get('db', 0)),
            password=redis_data.get('pass', None),
        )
        await self.redis.ping()
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self.loop = asyncio.create_task(self.captcha_loop())
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        if self.loop and not self.loop.cancelled():
            self.loop.cancel()
        if self.pubsub:
            await self.pubsub.close()

    async def captcha_loop(self):
        await self.bot.wait_until_ready()
        log.info('%s: Start Main Loop', self.__cog_name__)
        await self.pubsub.subscribe('red.captcha')
        while self is self.bot.get_cog('Captcha'):
            log.debug('captcha_loop:while')
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

            guild: discord.Guild = self.bot.get_guild(int(data['guild']))
            log.debug('guild: %s', guild)

            user_id = data['user']
            log.debug('user_id: %s', user_id)
            member: discord.Member = await guild.fetch_member(int(user_id))

            log.debug('data.requests: %s', data['requests'])
            resp = dict()
            if 'data' in data['requests']:
                resp = await self.process_get_data(guild, member)
            if 'verify' in data['requests']:
                resp = await self.process_verification(guild, member, data)
            log.debug('resp: %s', resp)
            pr = await self.redis.publish(channel, json.dumps(resp, default=str))
            log.debug('pr: %s', pr)
        except Exception as error:
            log.error('Exception processing message.')
            log.exception(error)

    async def process_get_data(self, guild: discord.Guild,
                               member: discord.Member,) -> dict:
        log.debug('process_members')
        config = await self.config.guild(guild).all()
        if not config['enabled']:
            return {'success': False}

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
        resp = {'success': True, 'member': member_data, 'guild': guild_data}

        verified_id: int = config['verified']
        verified: discord.Role = guild.get_role(verified_id)
        if verified in member.roles:
            resp.update({'success': True, 'verified': True})
        return resp

    async def process_verification(self, guild: discord.Guild,
                                   member: discord.Member,
                                   data: dict) -> dict:
        try:
            log.debug('data: %s', data)
            channel = data['channel']
            log.debug('channel: %s', channel)
            log.debug('guild.id: %s', guild.id)
            log.debug('member.id: %s', member.id)

            config = await self.config.guild(guild).all()
            if config['enabled']:
                role: discord.Role = guild.get_role(int(config['verified']))
                await member.add_roles(role)
                return {'success': True}
            else:
                return {'success': False, 'message': 'Disabled'}
        except Exception as error:
            log.exception(error)
            return {'success': False, 'message': str(error)}

    async def on_guild_join(self, guild: discord.Guild):
        pass

    # @commands.Cog.listener(name='on_message_without_command')
    # async def on_message_without_command(self, message: discord.Message):
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
    #     if conf['verified'] in message.author.roles:
    #         return
    #
    #     # User needs CAPTCHA verification - Need Web API
    #     channel = await message.author.create_dm()
    #     await channel.send('CAPTCHA Verification Required.')

    @commands.group(name='captcha', aliases=['cap'])
    @commands.guild_only()
    @commands.admin()
    async def captcha(self, ctx: commands.Context):
        """Options for manging CAPTCHA."""

    # @captcha.command(name='url', aliases=['u'])
    # async def captcha_url(self, ctx: commands.Context, url: str = ''):
    #     """Sets the CAPTCHA API URL."""
    #     log.debug('url: %s', url)
    #     # url = url.replace('/view', '').strip('/ ')
    #     # await self.config.guild(ctx.guild).url.set(url)
    #     # await ctx.send(f'✅ CAPTCHA API URL set to: <{url}>')

    @captcha.command(name='role', aliases=['r'])
    async def captcha_channel(self, ctx: commands.Context, *,
                              role: discord.Role):
        """Sets the CAPTCHA Role."""
        await self.config.guild(ctx.guild).verified.set(role.id)
        await ctx.send(f'✅ CAPTCHA role set to: `@{role.name}`')

    @captcha.command(name='enable', aliases=['e', 'on'])
    async def captcha_enable(self, ctx: commands.Context):
        """Enables CAPTCHA."""
        role_id = await self.config.guild(ctx.guild).verified()
        enabled = await self.config.guild(ctx.guild).enabled()
        if not role_id:
            await ctx.send('⛔ CAPTCHA role not set. Please set first.')
        elif enabled:
            await ctx.send('✅ CAPTCHA module already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('✅ CAPTCHA module enabled.')

    @captcha.command(name='disable', aliases=['d', 'off'])
    async def captcha_disable(self, ctx: commands.Context):
        """Disable CAPTCHA."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('✅ CAPTCHA module already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('✅ CAPTCHA module disabled.')

    @captcha.command(name='status', aliases=['s', 'settings'])
    async def captcha_status(self, ctx: commands.Context):
        """Get CAPTCHA status."""
        config = await self.config.guild(ctx.guild).all()
        role: discord.Role = ctx.guild.get_role(config['verified'])
        role_name = f'`@{role.name}`' if role else '⛔ **Not Set**'
        out = f'CAPTCHA Settings:\n' \
              f'Enabled: **{config["enabled"]}**\n' \
              f'Role: {role_name}\n' \
              f'Bots: {config["bots"]}'
        await ctx.send(out)

    @captcha.command(name='setup', aliases=['auto', 'a'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def captcha_setup(self, ctx: commands.Context):
        """AUTO Setup of CAPTCHA module."""

        bm: discord.Message = await ctx.send(
            'This will automatically setup CAPTCHA by removing most '
            'permissions from `@everyone` and adding a `verified` role with '
            'the current permissions of `@everyone`.\nProceed?'
        )
        pred = ReactionPredicate.yes_or_no(bm, ctx.author)
        start_adding_reactions(bm, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            await self.bot.wait_for('reaction_add', check=pred, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send('⛔ Request timed out. Aborting.', delete_after=60)
            await bm.delete()
            return

        if not pred.result:
            await ctx.send('⛔ Aborting.', delete_after=10)
            await bm.delete()
            return

        async with ctx.typing():
            await bm.clear_reactions()
            await bm.edit(content='⌛ Starting CAPTCHA Setup...')
            config = await self.config.guild(ctx.guild).all()
            log.debug(config)
            everyone: discord.Role = ctx.guild.get_role(ctx.guild.id)
            log.debug(everyone.permissions)

            if config['verified']:
                verified = ctx.guild.get_role(config['verified'])
            if not verified:
                await bm.edit(content='⌛ Creating Role `Verified`.')
                verified: discord.Role = await ctx.guild.create_role(
                    name='Verified',
                    permissions=everyone.permissions,
                )
                await self.config.guild(ctx.guild).verified.set(verified.id)

            await bm.edit(content='⌛ Adding `Verified` Role to all Members.')
            member: discord.Member
            async for member in AsyncIter(ctx.guild.members):
                if verified not in member.roles:
                    log.debug('Adding Role to: %s', member)
                    await member.add_roles(verified)

            await bm.edit(content='⌛ Creating `verification` Channel/Message.')
            everyone_overs = discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                add_reactions=False,
                send_messages=False,
            )
            verified_overs = discord.PermissionOverwrite(
                view_channel=False
            )
            overwrites = {everyone: everyone_overs, verified: verified_overs}
            channel: discord.TextChannel
            channel = await ctx.guild.create_text_channel(
                name='verification',
                overwrites=overwrites,
                position=0,
                reason='Server Verification Channel for New Members.',
                topic='Server Verification Channel for New Members.',
            )
            embed = discord.Embed()
            embed.title = '**IMPORTANT: ACTION REQUIRED**'
            embed.description = (
                'This server requires Human Verification to chat or speak.\n\n'
                'To complete verification, click the button below:\n\n'
                'Coming Soon. Check your DM (when the feature is done).'
            )
            await channel.send(embed=embed, view=VerifyView(self))

            await bm.edit(content='⌛ Updating `@everyone` permissions.')
            await everyone.edit(permissions=discord.Permissions.none())
            perms = discord.Permissions(
                connect=True,
                change_nickname=True,
                read_message_history=True,
                view_channel=True,
            )
            await everyone.edit(permissions=perms)

            await self.config.guild(ctx.guild).enabled.set(True)
            await bm.delete()
            await ctx.send(content='✅ All Done!')
