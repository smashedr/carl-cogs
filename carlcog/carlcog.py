import datetime
import os
import discord
import fuckit
import logging
import platform
import traceback
from typing import List, Optional, Union

from redbot.core import Config, commands, version_info
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.carlcog')


class Carlcog(commands.Cog):
    """Carl's Carlcog Cog"""

    carl_name = 'Carl Bot'
    carl_cogs = 'https://github.com/smashedr/carl-cogs'

    embedset_command = None
    forgetme_command = None
    info_command = None
    licenseinfo_command = None
    mydata_command = None
    ping_command = None
    uptime_command = None

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(alert_channel=None)
        self.info: Optional[dict] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        self.info = await self.bot.get_shared_api_tokens('info')
        log.info('INFO: %s', self.info)
        self.embedset_command = self.bot.remove_command('embedset')
        self.forgetme_command = self.bot.remove_command('forgetme')
        self.info_command = self.bot.remove_command('info')
        self.licenseinfo_command = self.bot.remove_command('licenseinfo')
        self.mydata_command = self.bot.remove_command('mydata')
        self.ping_command = self.bot.remove_command('ping')
        self.uptime_command = self.bot.remove_command('uptime')
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        with fuckit:
            self.bot.remove_command('embedset')
            self.bot.remove_command('forgetme')
            self.bot.remove_command('info')
            self.bot.remove_command('licenseinfo')
            self.bot.remove_command('mydata')
            self.bot.remove_command('ping')
            self.bot.remove_command('uptime')
        self.bot.add_command(self.embedset_command)
        self.bot.add_command(self.forgetme_command)
        self.bot.add_command(self.info_command)
        self.bot.add_command(self.licenseinfo_command)
        self.bot.add_command(self.mydata_command)
        self.bot.add_command(self.ping_command)
        self.bot.add_command(self.uptime_command)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Notify <alert_channel> when the bot leaves a server."""
        log.debug(guild)
        await self.process_guild_join_leave(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Notify <alert_channel> when the bot joins a server."""
        log.debug(guild)
        await self.process_guild_join_leave(guild, join=True)

    async def process_guild_join_leave(self, guild: discord.Guild, join=False):
        """TODO: This function may not work in 2+/3.5+"""
        channel_id = await self.config.alert_channel()
        if not channel_id:
            return
        channel = discord.VoiceChannel = self.bot.get_channel(channel_id)
        if not channel:
            log.warning('Channel %s not found.', channel_id)
            return

        # if guild.is_icon_animated():
        #     icon_url = guild.icon_url_as(format='gif')
        # else:
        #     icon_url = guild.icon_url_as(format='png')

        em = discord.Embed()

        if join:  # Joined
            created_at = int(guild.created_at.replace(tzinfo=datetime.timezone.utc).timestamp())
            description = (
                f'{self.bot.user.mention} joined a new server \U0001F4E5 \n\n'
                f'Created on **<t:{created_at}:D>** '
                f'over **<t:{created_at}:R>**'
            )
            em.colour = discord.Colour.green()
        else:  # Parted
            description = f'{self.bot.user.mention} left a server \U0001F4E4 \n'
            em.colour = discord.Colour.red()

        em.set_thumbnail(url=guild.icon.url)
        em.title = guild.name
        em.description = description
        em.add_field(name='Members', value=len(guild.members))
        em.add_field(name='Roles', value=len(guild.roles))
        em.add_field(name='Channels', value=len(guild.channels))
        em.add_field(name='Total Servers', value=len(self.bot.guilds))
        em.add_field(name='Total Users', value=len(self.bot.users))
        em.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await channel.send(embed=em)

    @commands.Cog.listener(name='on_command_error')
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Notify <alert_channel> when the bot catches an error."""
        log.debug(error)
        if isinstance(error, (
            commands.UserInputError,
            commands.DisabledCommand,
            commands.CommandNotFound,
            commands.CheckFailure,
            commands.NoPrivateMessage,
            commands.CommandOnCooldown,
            commands.MaxConcurrencyReached,
        )):
            return
        channel_id = await self.config.alert_channel()
        if not channel_id:
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            log.warning('Channel %s not found.', channel_id)
            return

        em = discord.Embed()
        em.colour = discord.Colour.red()
        em.title = f'Exception in command `{ctx.command.qualified_name}`'
        em.set_author(name='Jump to message', url=ctx.message.jump_url)
        em.description = ctx.message.content
        em.timestamp = ctx.message.created_at
        em.add_field(name='Invoker', value=ctx.author.mention)
        em.add_field(name='Channel', value=ctx.channel.mention or ctx.channel)
        if ctx.guild:
            em.add_field(name='Server', value=ctx.guild.name)
            em.set_thumbnail(url=ctx.guild.icon.url)
        else:
            em.set_thumbnail(url=self.bot.user.avatar.url)
        em.set_footer(text=f'ID: {ctx.author.id}', icon_url=ctx.author.avatar.url)
        await channel.send(embed=em)
        logs = ''.join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        for page in cf.pagify(logs):
            await channel.send(cf.box(page, lang='py'))

    @commands.command(name='setalertchannel', aliases=['sac'])
    @commands.is_owner()
    async def cc_set_alert_channel(self, ctx, channel: discord.TextChannel):
        """Sets the alert channel for various internal alerts."""
        try:
            await channel.send('Testing write access.', delete_after=15)
            await self.config.alert_channel.set(channel.id)
            await ctx.send(f'Updated alert channel to: {channel.mention}')
        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error setting channel to {channel}: {error}')

    @commands.command(name='prefix')
    @commands.admin()
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def cc_set_prefix(self, ctx, *, prefix: str = None):
        """Sets the <prefix(s)> for the server. Leave blank to reset."""
        await ctx.typing()
        if not prefix:
            await self.bot.set_prefixes([], ctx.guild)
            prefixes = await self.bot.get_valid_prefixes(ctx.guild)
            await ctx.send(f'Custom prefix reset to default: **{prefixes}**')
        else:
            prefixes = prefix.split()
            log.debug(prefixes)
            await self.bot.set_prefixes(prefixes, ctx.guild)
            await ctx.send(f'Prefixes for guild set to: **{prefixes}**')

    @commands.command(name='info', aliases=['about'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cc_info(self, ctx: commands.Context):
        """Bot uptime command."""
        scopes = ('bot', 'applications.commands')
        inv_url = discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions(8), scopes=scopes)

        py_ver = platform.python_version().replace('.', '')
        py_url = f'https://www.python.org/downloads/release/python-{py_ver}/'
        py_str = f'[{platform.python_version()}]({py_url})'

        dpy_url = f'https://github.com/Rapptz/discord.py/tree/v{discord.__version__}'
        dpy_str = f'[{discord.__version__}]({dpy_url})'

        red_url = f'https://github.com/Cog-Creators/Red-DiscordBot/tree/{version_info}'
        red_str = f'[{version_info}]({red_url})'

        desc_txt = 'My name is Carl and I am a fully functional Discord Bot.'
        # web_txt = ('For more information, to add me to your server, '
        #            'or manage my settings, visit the website at '
        #            '**[carl.sapps.me](https://carl.sapps.me/)**.')

        _py = '[Python](https://www.python.org/)'
        _dpy = '[discord.py](https://github.com/Rapptz/discord.py)'
        _red = '[Red Discord Bot](https://github.com/Cog-Creators/Red-DiscordBot)'
        _cc = f'[github.com/smashedr/carl-cogs]({self.carl_cogs})'
        _cogs = '[Cogs](https://index.discord.red/)'
        source_txt = (f'**{_cc}**\n\nI am written in {_py} using the {_dpy} framework ontop of the {_red} core. '
                      f'All commands are broken down into modules called {_cogs}. '
                      f'The source code for my cogs/commands can be found at [GitHub]({self.carl_cogs}).')

        owners_list: List[discord.User] = await self.get_owners(self.bot)
        owners = ', '.join([x.mention for x in owners_list])

        em = discord.Embed(
            title=self.carl_name,
            url=self.carl_cogs,
            description=desc_txt,
            color=discord.Colour(int('6F42C1', 16)),
            timestamp=ctx.message.created_at,
        )
        em.set_thumbnail(url=self.bot.user.avatar.url)
        em.set_author(name=str(self.bot.user), url=inv_url)

        em.add_field(name='Python', value=py_str)
        em.add_field(name='Discord.py', value=dpy_str)
        em.add_field(name='Red', value=red_str)
        em.add_field(name='Owners', value=owners)
        # em.add_field(name='Visit Dashboard', value=web_txt, inline=False)
        em.add_field(name='View Source', value=source_txt, inline=False)

        em.set_footer(text=f'Requested by {ctx.author.display_name}', icon_url=ctx.author.avatar.url)
        buttons = {
            'Add to Server': inv_url,
            # 'Open Dashboard': 'https://carl.sapps.me/',
        }
        if 'status' in self.info:
            buttons['Status'] = self.info['status']
        await ctx.send(embed=em, view=ButtonsURLView(buttons))

    @commands.command(name='uptime', aliases=['up', 'latency'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cc_uptime(self, ctx: commands.Context):
        """Bot uptime command."""
        bot_ts = self.bot.uptime.replace(tzinfo=datetime.timezone.utc).timestamp()
        bot_delta = datetime.datetime.utcnow() - self.bot.uptime
        em = discord.Embed()
        em.colour = discord.Colour.green()
        em.set_thumbnail(url=self.bot.user.avatar.url)
        em.set_author(name=self.bot.user, url='https://carl.sapps.me/')
        em.title = 'Bot Uptime'
        em.description = f'Started <t:{int(bot_ts)}:D>. Over <t:{int(bot_ts)}:R>.'
        unit_details = self.format_timedelta(bot_delta)
        em.add_field(
            name=f'Total: {cf.humanize_timedelta(timedelta=bot_delta)}',
            value=cf.box(unit_details, lang='diff'),
            inline=False,
        )
        value = 'Bot latency: {}ms'.format(str(round(self.bot.latency * 1000, 2)))
        for shard, time in self.bot.latencies:
            value += f'\nShard {shard + 1}/{len(self.bot.latencies)}: {round(time * 1000)}ms'

        em.add_field(
            name='Shard and Latency Stats',
            value=cf.box(value, lang='yaml'),
            inline=False,
        )
        em.timestamp = datetime.datetime.now(datetime.timezone.utc)
        if 'status' in self.info:
            buttons = {'Status': self.info['status']}
            view = ButtonsURLView(buttons)
        else:
            view = None
        await ctx.send(embed=em, view=view)

    @staticmethod
    async def get_owners(bot, ids=False) -> List[Union[discord.User, int]]:
        app_info = await bot.application_info()
        owners: List[discord.User] = [app_info.owner]
        if os.environ.get('CO_OWNER'):
            for owner_id in os.environ.get('CO_OWNER').split(','):
                owners.append(bot.get_user(int(owner_id)))
        if ids:
            return [x.id for x in owners]
        return owners

    @staticmethod
    def format_timedelta(delta: datetime.timedelta):
        def clean_format(d: datetime.timedelta, u: str):
            mapper = {'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400}
            return cf.humanize_number(d.total_seconds() // mapper[u])

        data = {}
        units = ('seconds', 'minutes', 'hours', 'days')
        for unit in units:
            data[unit] = str(clean_format(delta, unit))

        unit_details = '\n'.join(f'+ {data[x]} {x}' for x in units)
        return unit_details


class ButtonsURLView(discord.ui.View):
    def __init__(self, buttons: dict[str, str]):
        super().__init__()
        for label, url in buttons.items():
            self.add_item(discord.ui.Button(label=label, url=url))
