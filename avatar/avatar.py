import datetime
import discord
import httpx
import io
import logging
import random
import validators
from typing import Any, Dict, List, Optional, Tuple, Union

from discord.ext import tasks
from redbot.core import app_commands, commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.avatar')


class Avatar(commands.Cog):
    """Carl's Avatar Cog"""

    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    frequency = {
        'hourly': ['hour', 'hourly'],
        'daily': ['day', 'daily'],
        'weekly': ['week', 'weekly'],
        # 'monthly': ['month', 'monthly'],
    }

    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }

    guild_default = {
        'avatars': [],
        'enabled': False,
        'hour': 9,
        'day': 1,
        'frequency': 'weekly',
        'recent': [],
        'last': None,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        self.update_avatar.start()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.update_avatar.cancel()

    @tasks.loop(minutes=60.0)
    async def update_avatar(self):
        await self.bot.wait_until_ready()
        log.info('%s: Update Avatar Task', self.__cog_name__)
        current = datetime.datetime.now()
        log.info('Day: %s Hour: %s', current.isoweekday(), current.hour)
        all_guilds: Dict[int, dict] = await self.config.all_guilds()
        async for guild_id, data in AsyncIter(all_guilds.items(), delay=5, steps=10):
            if not data['enabled'] or len(data['avatars']) < 2:
                log.debug('Guild %s Disabled or No Avatars', guild_id)
                continue

            if data['last']:
                last = datetime.datetime.fromtimestamp(data['last'])
                seconds: int = (current - last).seconds
            else:
                seconds: int = 1 + 60*60*24
                log.warning('Guild %s NO LAST FOUND, setting to: %s', guild_id, seconds)

            if data['frequency'] == 'hourly':
                if seconds > (60*30):
                    await self.process_avatar_update(guild_id, current)
                else:
                    log.debug('Guild %s on COOLDOWN: %s', guild_id, seconds)
                continue

            if data['frequency'] == 'daily':
                if data['hour'] != current.hour:
                    log.debug('Guild %s wrong HOUR: %s', guild_id, data['hour'])
                else:
                    if seconds > (60*60*1):
                        await self.process_avatar_update(guild_id, current)
                    else:
                        log.debug('Guild %s on COOLDOWN: %s', guild_id, seconds)
                continue

            if data['frequency'] == 'weekly':
                if data['hour'] != current.hour:
                    log.debug('Guild %s wrong HOUR: %s', guild_id, data['hour'])
                elif data['day'] != current.isoweekday():
                    log.debug('Guild %s wrong DAY: %s', guild_id, data['day'])
                else:
                    if seconds > (60*60*24):
                        await self.process_avatar_update(guild_id, current)
                    else:
                        log.debug('Guild %s on COOLDOWN: %s', guild_id, seconds)
                continue

            log.error('NO FREQUENCY MATCH: %s', guild_id)
            # if data['frequency'] == 'monthly':
            #     if data['day'] != current.isoweekday():
            #         log.debug('Guild %s wrong day: %s', guild_id, data['day'])
            #     else:
            #         await self.process_avatar_update(guild_id)
            #     continue

    async def process_avatar_update(self, guild: Union[discord.Guild, int, str],
                                    dt: datetime.datetime) -> Optional[bool]:
        log.debug('process_avatar_update')
        if isinstance(guild, (int, str)):
            guild: discord.Guild = self.bot.get_guild(int(guild))
        log.debug('guild.id: %s', guild.id)
        data: Dict[str, Any] = await self.config.guild(guild).all()
        avatars = data['avatars']
        random.shuffle(avatars)
        for avatar in avatars:
            if avatar in data['recent']:
                continue
            new_avatar = avatar
            data['recent'].append(new_avatar)
            break
        else:
            data['recent'].clear()
            new_avatar = random.choice(avatars)
            data['recent'].append(new_avatar)

        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(new_avatar)
            if not r.is_success:
                # TODO: Handle the stupid error
                log.error('Error: %s: %s', r.status_code, r.text)
                return
        file = io.BytesIO(r.content)
        await guild.edit(icon=file.getvalue(), reason='Avatar Rotation')
        data['last'] = dt.timestamp()
        await self.config.guild(guild).set(data)
        log.debug('Updated Guild %s Avatar to: %s', guild.id, new_avatar)
        return True

    @commands.hybrid_group(name='avatar')
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def _avatar(self, ctx: commands.Context):
        """Avatar Command"""

    @_avatar.command(name='rotate', aliases=['change'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def _avatar_rotate(self, ctx: commands.Context):
        """Rotate to a New Avatar."""
        await ctx.typing()
        data: Dict[str, Any] = await self.config.guild(ctx.guild).all()
        if len(data['avatars']) < 2:
            return await ctx.send('⛔ You need to add at least 2 Avatars for this to work.')
        current = datetime.datetime.now()
        if data['last']:
            log.debug('last: %s', data['last'])
            last = datetime.datetime.fromtimestamp(data['last'])
            seconds: float = (current - last).seconds
        else:
            seconds: float = 0
        log.debug('seconds: %s', seconds)
        if seconds < 300:
            return await ctx.send(f'⛔ Avatar Rotation on hard cooldown for {300-seconds} more seconds.')

        update = await self.process_avatar_update(ctx.guild, current)
        if not update:
            await ctx.send('⛔ Error processing Avatar update. Check Logs.')
        else:
            await ctx.send('✅ Avatar Manually Rotated.')

    @_avatar.command(name='hour', aliases=['time'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @app_commands.describe(hour='Hour of the Day in UTC')
    async def _avatar_hour(self, ctx: commands.Context, hour: int):
        """Set Avatar Update Hour."""
        await ctx.typing()
        log.debug('hour: %s', hour)
        hour = int(hour)
        if not -1 < int(hour) < 23:
            content = (f'⛔ Unable to determine Hour of Day from input: {hour}.\n'
                       f'Hour should be a number 0 to 23')
            return await ctx.send(content)
        await self.config.guild(ctx.guild).hour.set(int(hour))
        await ctx.send(f'✅ {self.__cog_name__} change hour updated to UTC: `{hour}`')

    @_avatar.command(name='day')
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @app_commands.describe(day='Day of the Week')
    async def _avatar_day(self, ctx: commands.Context, day: str):
        """Set Avatar Update Day."""
        await ctx.typing()
        log.debug('day: %s', day)
        if day.isdigit() and 0 < int(day) < 8:
            dow = int(day)
        else:
            for d, name in self.days:
                if day.lower() in name:
                    dow = d
                    break
            else:
                content = (f'⛔ Unable to determine Day of Week from input: {day}.\n'
                           f'Day should be 1-7 or: {cf.humanize_list(self.days)}')
                return await ctx.send(content)
        await self.config.guild(ctx.guild).day.set(int(dow))
        await ctx.send(f'✅ {self.__cog_name__} change day updated to: `{self.days[dow-1]}`')

    @_avatar.command(name='frequency', aliases=['update'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @app_commands.describe(frequency='Daily, Weekly, or Monthly')
    async def _avatar_frequency(self, ctx: commands.Context, frequency: str):
        """Set Avatar Update Frequency"""
        await ctx.typing()
        frequency = frequency.lower()
        log.debug('frequency: %s', frequency)
        for freq, items in self.frequency.items():
            if frequency in items:
                new_freq = freq
                break
        else:
            content = (f'⛔ Unable to determine Update Frequency from input: {frequency}.\n'
                       f'Frequency should be: {cf.humanize_list(list(self.frequency.keys()))}')
            return await ctx.send(content)
        await self.config.guild(ctx.guild).frequency.set(new_freq)
        await ctx.send(f'✅ {self.__cog_name__} frequency updated to: `{new_freq}`')

    @_avatar.command(name='enable', aliases=['e', 'on'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def _avatar_enable(self, ctx: commands.Context):
        """Enable Avatar."""
        await ctx.typing()
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send(f'⛔ {self.__cog_name__} already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send(f'✅ {self.__cog_name__} has been enabled.')

    @_avatar.command(name='disable', aliases=['d', 'off'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def _avatar_disable(self, ctx: commands.Context):
        """Disable Avatar."""
        await ctx.typing()
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send(f'⛔ {self.__cog_name__} already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send(f'✅ {self.__cog_name__} has been disabled.')

    @_avatar.command(name='status', aliases=['s', 'settings'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def _avatar_status(self, ctx: commands.Context):
        """Get Avatar status."""
        await ctx.typing()
        data: Dict[str, Any] = await self.config.guild(ctx.guild).all()
        enabled = '✅ ENABLED' if data['enabled'] else '⛔ DISABLED'
        content = (
            f"{self.__cog_name__} Settings:\n```ini\n"
            f"[Status]:    {enabled}\n"
            f"[Frequency]: {data['frequency']}\n"
            f"[UTC Hour]:  {data['hour']}\n"
            f"[Day]:       {self.days[data['day']-1]}\n"
            f"[Avatars]:   {len(data['avatars'])}\n"
            f"[Status]:    {len(data['recent'])}/{len(data['avatars'])}\n"
            f"```"
        )
        await ctx.send(content)

    @_avatar.command(name='clear', aliases=['empty', 'reset'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _avatar_clear(self, ctx: commands.Context):
        """Remove ALL Avatar's from the random Avatar list."""
        await ctx.typing()
        await self.config.guild(ctx.guild).avatars.set([])
        await ctx.send('🔥 All stored Avatars were burnt alive.')

    @_avatar.command(name='list', aliases=['show'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _avatar_list(self, ctx: commands.Context):
        """List all Avatar's in the random Avatar list."""
        await ctx.typing()
        avatars: List[str] = await self.config.guild(ctx.guild).avatars()
        if len(avatars) < 1:
            return await ctx.send('⛔ No stored avatars found. Add some first...')
        lines = [f'🖼️ Stored Avatars: `{len(avatars)}`']
        for avatar in avatars:
            lines.append(f'<{avatar}>')
        await ctx.send('\n'.join(lines))

    @_avatar.command(name='add')
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    @app_commands.describe(avatar_urls='One or More Avatar URLs')
    async def _avatar_add(self, ctx: commands.Context, *, avatar_urls: str):
        """Add one or more Avatar's to server random Avatar list."""
        await ctx.typing()
        good, bad = await self.parse_urls(avatar_urls)
        log.debug('good: %s', good)
        log.debug('bad: %s', bad)
        avatars: List[str] = await self.config.guild(ctx.guild).avatars() + good
        await self.config.guild(ctx.guild).avatars.set(avatars)
        if bad:
            bad_out = '\n'.join([f'<{x}>' for x in bad])
            await ctx.send(f'⛔ The following URLs could not be parsed:\n{bad_out}')
        good_out = '\n'.join([f'<{x}>' for x in good])
        content = f'✅ Added the following Avatar URLs to the list:\n{good_out}'
        await ctx.send(content)

    async def parse_urls(self, string: str) -> Tuple[Optional[List[str]], Optional[List[str]]]:
        good, bad = [], []
        url_list = string.strip('` ').split()
        for url in url_list:
            if validators.url(url):
                async with httpx.AsyncClient(**self.http_options) as client:
                    r = await client.head(url)
                    if r.is_success:
                        good.append(str(r.url))
                        continue
            bad.append(url)
        return good, bad


# class ModalView(discord.ui.View):
#     def __init__(self, cog: commands.Cog, data: Dict[str, str]):
#         super().__init__(timeout=None)
#         self.cog = cog
#         self.data: Dict[str, str] = data
#
#     @discord.ui.button(label='Set Zipline Details', emoji='🖼️', style=discord.ButtonStyle.blurple)
#     async def set_zipline(self, interaction: discord.interactions.Interaction, button: discord.Button):
#         log.debug(interaction)
#         log.debug(button)
#         user = interaction.user
#         user_config: Dict[str, Any] = await self.cog.config.user(user).all()
#         modal = DataModal(view=self, data=user_config)
#         await interaction.response.send_modal(modal)
#
#
# class DataModal(discord.ui.Modal):
#     def __init__(self, view: discord.ui.View, data: Dict[str, Any]):
#         super().__init__(title='Set Zipline Details')
#         self.view: discord.ui.View = view
#         self.data: Dict[str, Any] = data
#         self.base_url = discord.ui.TextInput(
#             label='Zipline Base URL',
#             placeholder='Ex: https://example.com/dashboard',
#             default=self.data.get('base_url'),
#             style=discord.TextStyle.short,
#             max_length=255,
#             min_length=10,
#         )
#         self.add_item(self.base_url)
#         self.zip_token = discord.ui.TextInput(
#             label='Zipline Authorization Token',
#             placeholder='Ex: alRLdlKDFJ31FckdfjEndu5n.AL4nxkdkMjerLqMAPA',
#             default=self.data.get('zip_token'),
#             style=discord.TextStyle.short,
#             max_length=43,
#             min_length=43,
#         )
#         self.add_item(self.zip_token)
#
#     async def on_submit(self, interaction: discord.Interaction):
#         # discord.interactions.InteractionResponse
#         log.debug('ReplyModal - on_submit')
#         # message: discord.Message = interaction.message
#         user: discord.Member = interaction.user
#         # TODO: Verify Settings Here
#         user_config = {
#             'base_url': self.base_url.value.rstrip('dashboard').strip('/ '),
#             'zip_token': self.zip_token.value.strip(),
#         }
#         await self.view.cog.config.user(user).set(user_config)
#         log.debug(user_config)
#         msg = "✅ Zipline Details Updated Successfully..."
#         await interaction.response.send_message(msg, ephemeral=True)
