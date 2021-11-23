import datetime
import discord
import logging
import traceback
from io import BytesIO
from pyppeteer import launch

from redbot.core import Config, commands
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.carlcog')


class Carlcog(commands.Cog):
    """Carl's Carlcog Cog"""
    uptime_command = None

    def __init__(self, bot):
        self.bot = bot
        self.chrome = '/data/local-chromium/588429/chrome-linux/chrome'
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(alert_channel=None)

    def cog_load(self) -> None:
        log.info('Initializing Carlcog Cog')
        self.uptime_command = self.bot.remove_command('uptime')

    def cog_unload(self):
        log.info('Unload Carlcog Cog')
        try:
            self.bot.remove_command('uptime')
        except Exception as error:
            log.debug(error)
        self.bot.add_command(self.uptime_command)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Notify a channel when the bot leaves a server."""
        log.debug(guild)
        await self.process_guild_join_leave(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Notify a channel when the bot joins a server."""
        log.debug(guild)
        await self.process_guild_join_leave(guild, join=True)

    async def process_guild_join_leave(self, guild: discord.Guild, join=False):
        """Notify a channel when the bot joins a server."""
        channel_id = await self.config.alert_channel()
        if not channel_id:
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            log.warning('Channel %s not found.', channel_id)
            return

        if guild.is_icon_animated():
            icon_url = guild.icon_url_as(format='gif')
        else:
            icon_url = guild.icon_url_as(format='png')

        em = discord.Embed(color=guild.me.color)

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

        em.set_thumbnail(url=icon_url)
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
        """Logs errors to the alert_channel."""
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
            em.set_thumbnail(url=ctx.guild.icon_url)
        else:
            em.set_thumbnail(url=self.bot.user.avatar_url)
        em.set_footer(text=f'ID: {ctx.author.id}', icon_url=ctx.author.avatar_url)
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
        await ctx.trigger_typing()
        if not prefix:
            await self.bot.set_prefixes([], ctx.guild)
            prefixes = await self.bot.get_valid_prefixes(ctx.guild)
            await ctx.send(f'Custom prefix reset to default: **{prefixes}**')
        else:
            prefixes = prefix.split()
            log.debug(prefixes)
            await self.bot.set_prefixes(prefixes, ctx.guild)
            await ctx.send(f'Prefixes for guild set to: **{prefixes}**')

    @commands.command(name='checksite', aliases=['cs'])
    @commands.cooldown(2, 15, commands.BucketType.user)
    async def cc_check_site(self, ctx, url: str):
        """Check the status of a site at given <url>"""
        async with ctx.channel.typing():
            try:
                url = url.strip('<>')
                log.debug(url)
                browser = await launch(
                    executablePath=self.chrome, args=['--no-sandbox'])
                page = await browser.newPage()
                await page.setViewport({'width': 1280, 'height': 960})
                await page.goto(url, timeout=1000 * 12)
                result = await page.screenshot()
                await browser.close()
                data = BytesIO()
                data.write(result)
                data.seek(0)
                file = discord.File(data, filename='screenshot.png')
                await ctx.send(f'Results for: `{url}`', files=[file])
            except Exception as error:
                log.exception(error)
                await ctx.send(error)

    @commands.command(name='uptime', aliases=['up'])
    @commands.cooldown(2, 10, commands.BucketType.guild)
    async def cc_uptime(self, ctx: commands.Context):
        """Bot uptime command."""
        bot_ts = self.bot.uptime.replace(tzinfo=datetime.timezone.utc).timestamp()
        bot_delta = datetime.datetime.utcnow() - self.bot.uptime
        description = f'Started <t:{int(bot_ts)}:D>. Over <t:{int(bot_ts)}:R>.'
        em = discord.Embed()
        em.colour = discord.Colour.green()
        em.set_thumbnail(url=self.bot.user.avatar_url)
        em.set_author(name=self.bot.user, url='https://carl.sapps.me/')
        em.title = "Bot Uptime"
        unit_details = self.format_timedelta(bot_delta)
        em.add_field(
            name=f'Total: {cf.humanize_timedelta(seconds=int(bot_delta.seconds))}',
            value=description + cf.box(unit_details, lang="diff"),
            inline=False,
        )
        value = "Bot latency: {}ms".format(str(round(self.bot.latency * 1000, 2)))
        for shard, time in self.bot.latencies:
            value += f"\nShard {shard + 1}/{len(self.bot.latencies)}: {round(time * 1000)}ms"

        em.add_field(
            name="Shard and Latency Stats",
            value=cf.box(value, lang="yaml"),
            inline=False,
        )
        em.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await ctx.send(embed=em)

    @staticmethod
    def format_timedelta(delta: datetime.timedelta):
        def clean_format(d: datetime.timedelta, u: str):
            mapper = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}
            return cf.humanize_number(d.total_seconds() // mapper[u])

        data = {}
        units = ("seconds", "minutes", "hours", "days")
        for unit in units:
            data[unit] = str(clean_format(delta, unit))

        unit_details = "\n".join(f"+ {data[x]} {x}" for x in units)
        return unit_details
