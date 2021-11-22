import datetime
import discord
import itertools
import logging

from tabulate import tabulate
from typing import Optional, Union

from redbot.core import commands
from redbot.core.utils import chat_formatting as cf
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS, close_menu

from .converters import CarlRoleConverter, CarlChannelConverter, FuzzyMember

logger = logging.getLogger('red.botutils')


class Botutils(commands.Cog):
    """Carl's Botutils Cog"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self) -> None:
        logger.info('Loading Botutils Cog')

    def cog_unload(self) -> None:
        logger.info('Unloading Botutils Cog')

    @commands.command(name='guildid', aliases=['gid', 'sid', 'serverid'])
    @commands.guild_only()
    async def guild_id(self, ctx):
        """Get the ID for the guild."""
        await ctx.trigger_typing()
        await ctx.send(f'\U0000269C **{ctx.guild.name}** ID: `{ctx.guild.id}`')

    @commands.command(name='emojiid', aliases=['eid'])
    @commands.guild_only()
    async def emoji_id(self, ctx, emoji: discord.Emoji):
        """Get the ID for an <emoji>."""
        await ctx.trigger_typing()
        await ctx.send(f'**{emoji}** ID: `{emoji.id}`')

    @commands.command(name='roleid', aliases=['rid'])
    @commands.guild_only()
    async def role_id(self, ctx, *, role: Union[CarlRoleConverter, discord.Role]):
        """Get the ID for a <role>."""
        await ctx.trigger_typing()
        await ctx.send(f'{role.mention} ID: `{role.id}`')

    @commands.command(name='channelid', aliases=['cid'])
    @commands.guild_only()
    async def channel_id(self, ctx, *,
                         channel: Optional[Union[CarlChannelConverter,
                                                 discord.TextChannel,
                                                 discord.VoiceChannel,
                                                 discord.CategoryChannel,
                                                 discord.StageChannel]]):
        """Get the ID for a <channel>."""
        await ctx.trigger_typing()
        if len(ctx.message.content.split()) == 1:
            channel = channel or ctx.channel
        if not channel:
            user_input = ctx.message.content.split()
            user_input.pop(0)
            user_input = ' '.join(user_input)
            await ctx.send(f'Channel "{user_input}" not found.')
            return

        emoji = self.channel_type_emoji(channel)
        if str(channel.type) == 'text':
            channel_string = f'{emoji} **#{channel}**'
        else:
            channel_string = f'{emoji} **{channel}**'
        await ctx.send(f'{channel_string} ID: `{channel.id}`')

    @commands.command(name='userid', aliases=['uid'])
    @commands.guild_only()
    async def user_id(self, ctx, user: Optional[FuzzyMember], first: Optional[Union[bool, str]]):
        """Get the ID(s) for a <user>. Defaults to current user or a FuzzyMatch."""
        await ctx.trigger_typing()
        if len(ctx.message.content.split()) == 1:
            user = user or [ctx.author]
        if not user:
            user_input = ctx.message.content.split().pop(1)
            await ctx.send(f'User "{user_input}" not found.')
            return

        if len(user) == 1 or first:
            await ctx.send(f'\N{BUST IN SILHOUETTE} **{user[0]}:** `{user[0].id}`')
            return

        table = [['Name', 'Display Name', 'ID']]
        for u in user:
            table.append([str(u), u.display_name, u.id])
        msg = tabulate(table, headers='firstrow')

        pages = []
        for page in cf.pagify(msg, delims=['\n'], page_length=1200):
            pages.append(cf.box(page))
        if len(pages) == 1:
            controls = {'\N{CROSS MARK}': close_menu}
            await menu(ctx, pages, controls, timeout=60)
        else:
            await menu(ctx, pages, DEFAULT_CONTROLS, timeout=60)

    @commands.command(name='emojiinfo', aliases=['einfo'])
    @commands.guild_only()
    async def emoji_info(self, ctx, emoji: discord.Emoji):
        """Get Emoji information for <emoji>."""
        msg = (
            f'**Emoji** {str(emoji)}\n'
            f'```ini\n'
            f'[NAME]:       {emoji.name}\n'
            f'[GUILD]:      {emoji.guild}\n'
            f'[ID]:         {emoji.id}\n'
            f'[ANIMATED]:   {emoji.animated}\n'
            f'[URL]:\n{emoji.url}'
            '```'
        )
        await ctx.send(msg)

    @commands.command(name='guildinfo', aliases=['ginfo', 'sinfo', 'serverinfo'])
    @commands.guild_only()
    async def guild_info(self, ctx, *, guild: Optional[discord.Guild]):
        """Shows information for the <guild>."""
        if len(ctx.message.content.split()) == 1:
            guild = guild or ctx.guild
        if not guild:
            user_input = ctx.message.content.split()
            user_input.pop(0)
            user_input = ' '.join(user_input)
            await ctx.send(f'Guild "{user_input}" not found.')
            return

        await self.show_guild_info(ctx, guild)

    @classmethod
    async def show_guild_info(cls, ctx, guild: discord.Guild):
        msg = await ctx.send('**Guild**```\nLoading guild info...```')

        online = str(len([m.status for m in guild.members if str(m.status) == 'online' or str(m.status) == 'idle']))
        text_channels = [x for x in guild.channels if isinstance(x, discord.TextChannel)]
        voice_channels = [x for x in guild.channels if isinstance(x, discord.VoiceChannel)]
        if guild.is_icon_animated():
            icon_url = guild.icon_url_as(format='gif')
        else:
            icon_url = guild.icon_url_as(format='png')
        banner_url = guild.banner_url_as(format='jpeg')
        splash_url = guild.splash_url_as(format='jpeg')

        data = f'**Guild**```ini\n'
        data += f'[Name]:       {guild.name}\n'
        data += f'[ID]:         {guild.id}\n'
        data += f'[Owner]:      {guild.owner}\n'
        data += f'[Users]:      {online}/{len(guild.members)}\n'
        data += f'[Text]:       {len(text_channels)}\n'
        data += f'[Voice]:      {len(voice_channels)}\n'
        data += f'[Emojis]:     {len(guild.emojis)}\n'
        data += f'[Roles]:      {len(guild.roles)}\n'
        data += f'[Created]:    {cls.time_since(guild.created_at)}\n'
        data += f'[Avatar URL]:\n{icon_url}\n'
        if banner_url:
            data += f'[Banner URL]:\n{banner_url}\n'
        if splash_url:
            data += f'[Splash URL]:\n{splash_url}\n'
        data += '```'

        await msg.edit(content=data)

    @commands.command(name='roleinfo', aliases=['rinfo'])
    @commands.guild_only()
    async def role_info(self, ctx, *, role: Union[CarlRoleConverter, discord.Role]):
        """Shows role info for <role>."""
        await self.show_role_info(ctx, role)

    @classmethod
    async def show_role_info(cls, ctx, role: discord.Role):
        embed = discord.Embed(description='Gathering role stats...', color=role.color)
        msg = await ctx.send('**Role**', embed=embed)

        perms_yes, perms_no = [], []
        for x in sorted(iter(role.permissions)):
            if 'True' in str(x):
                perms_yes.append(str(x).split("'")[1])
            else:
                perms_no.append(str(x).split("'")[1])
        total_users = str(len([m for m in role.guild.members if role in m.roles]))

        em = discord.Embed(colour=role.colour)
        em.add_field(name='Guild', value=role.guild.name)
        em.add_field(name='Role Name', value=role.name)
        em.add_field(name='Created', value=cls.time_since(role.created_at))
        em.add_field(name='Users in Role', value=total_users)
        em.add_field(name='ID', value=role.id)
        em.add_field(name='Color', value=role.color)
        em.add_field(name='Position', value=role.position)
        em.add_field(name='Valid Permissions', value='{}'.format('\n'.join(perms_yes) or 'None'))
        em.add_field(name='Invalid Permissions', value='{}'.format('\n'.join(perms_no) or 'None'))
        em.set_thumbnail(url=role.guild.icon_url)
        await msg.edit(embed=em)

    @commands.command(name='userinfo', aliases=['uinfo'])
    @commands.guild_only()
    async def user_info(self, ctx, user: Optional[Union[discord.Member, discord.User]]):
        """Shows information on <user>. Defaults to author."""
        if len(ctx.message.content.split()) == 1:
            user = user or ctx.author
        if not user:
            user_input = ctx.message.content.split().pop(1)
            await ctx.send(f'User "{user_input}" not found.')
            return

        await self.show_user_info(ctx, user)

    async def show_user_info(self, ctx, user: Union[discord.Member, discord.User]):
        msg = await ctx.send('**User**```\nLoading user info...```')

        seen = str(len(set([member.guild.name for member in self.bot.get_all_members() if member.id == user.id])))
        if user.is_avatar_animated():
            icon_url = user.avatar_url_as(format='gif')
        else:
            icon_url = user.avatar_url_as(format='png')

        data = '**User**```ini\n'
        data += '[Name]:          {}\n'.format(cf.escape(str(user)))
        data += '[ID]:            {}\n'.format(user.id)
        data += '[Created]:       {}\n'.format(self.time_since(user.created_at))
        data += '[Servers]:       {} shared\n'.format(seen)
        if isinstance(user, discord.Member):
            if actplay := discord.utils.get(user.activities, type=discord.ActivityType.playing):
                data += '[Playing]:       {}\n'.format(cf.escape(str(actplay.name)))
            if actlisten := discord.utils.get(user.activities, type=discord.ActivityType.listening):
                if isinstance(actlisten, discord.Spotify):
                    _form = '{} - {}'.format(actlisten.artist, actlisten.title)
                else:
                    _form = actlisten.name
                data += '[Listening]:     {}\n'.format(cf.escape(_form))
            if actwatch := discord.utils.get(user.activities, type=discord.ActivityType.watching):
                data += '[Watching]:      {}\n'.format(cf.escape(str(actwatch.name)))
            if actstream := discord.utils.get(user.activities, type=discord.ActivityType.streaming):
                data += '[Streaming]: [{}]({})\n'.format(cf.escape(str(actstream.name)), cf.escape(actstream.url))
            if actcustom := discord.utils.get(user.activities, type=discord.ActivityType.custom):
                if actcustom.name is not None:
                    data += '[Custom status]: {}\n'.format(cf.escape(str(actcustom.name)))
            roles = [r.name for r in user.roles if r.name != '@everyone']
            data += '[Status]:        {}\n'.format(user.status)
            data += '[Guild]:         {}\n'.format(user.guild)
            data += '[Joined]:        {}\n'.format(self.time_since(user.joined_at))
            data += '[In Voice]:      {}\n'.format(user.voice.channel if user.voice else None)
            data += '[AFK]:           {}\n'.format(user.voice.afk if user.voice else False)
            data += '[Roles]:         {}\n'.format(', '.join(roles))
            data += '[Avatar URL]:\n{}\n'.format(icon_url)
        data += '```'

        await msg.edit(content=data)

    @commands.command(name='channelinfo', aliases=['cinfo', 'chinfo'])
    @commands.guild_only()
    async def channel_info(self, ctx, *, channel: CarlChannelConverter = None):
        """Shows channel information. Defaults to current text channel."""
        channel = channel or ctx.channel
        await self.show_channel_info(ctx, channel)

    @classmethod
    async def show_channel_info(cls, ctx,
                                channel: Optional[Union[discord.TextChannel,
                                                        discord.VoiceChannel,
                                                        discord.CategoryChannel,
                                                        discord.StageChannel]]):
        channel_type = str(channel.type).title()
        msg = await ctx.send(f'**Channel: {channel_type}**'
                             f'```\nLoading channel info...```')

        yesno = {True: 'Yes', False: 'No'}

        data = f'**Channel: {channel_type}**```ini\n'
        data += '[Server]:     {}\n'.format(channel.guild.name)
        data += '[Name]:       {}\n'.format(cf.escape(str(channel)))
        data += '[ID]:         {}\n'.format(channel.id)
        data += '[Private]:    {}\n'.format(yesno[isinstance(channel, discord.abc.PrivateChannel)])
        if getattr(channel, 'topic', None):
            data += '[Topic]:      {}\n'.format(channel.topic)
        data += '[Position]:   {}\n'.format(channel.position)
        data += '[Created]:    {}\n'.format(cls.time_since(channel.created_at))
        data += '[Type]:       {}\n'.format(channel_type)
        if isinstance(channel, discord.VoiceChannel):
            data += '[Users]:      {}\n'.format(len(channel.members))
            data += '[User limit]: {}\n'.format(channel.user_limit)
            data += '[Bitrate]:    {}kbps\n'.format(int(channel.bitrate / 1000))
        data += '```'

        await msg.edit(content=data)

    @commands.command(name='idinfo', aliases=['id', 'getid'])
    @commands.guild_only()
    async def id_info(self, ctx, check_id: int):
        """Resolve any ID to a Channel, Emoji, Guild, Role or User."""
        await ctx.trigger_typing()
        result = None
        if ctx.guild.id == check_id:
            result = ctx.guild
        elif ctx.channel.id == check_id:
            result = ctx.channel
        elif ctx.author.id == check_id:
            result = ctx.author

        if not result:
            check_local = (
                    ctx.guild.roles
                    + list(ctx.guild.emojis)
                    + ctx.guild.members
                    + ctx.guild.channels
            )
            result = discord.utils.get(check_local, id=check_id)

        if not result:
            roles = [g.roles for g in self.bot.guilds]
            check_all = (
                    self.bot.guilds + self.bot.emojis
                    + list(itertools.chain.from_iterable(roles))
                    + [m for m in self.bot.get_all_members()]
                    + [c for c in self.bot.get_all_channels()]
            )
            result = discord.utils.get(check_all, id=check_id)

        if isinstance(result, discord.Emoji):
            await ctx.invoke(self.emoji_info, result)
        elif isinstance(result, discord.Guild):
            await self.show_guild_info(ctx, result)
        elif isinstance(result, discord.Role):
            await self.show_role_info(ctx, result)
        elif isinstance(result, discord.abc.GuildChannel):
            await self.show_channel_info(ctx, result)
        elif isinstance(result, (discord.Member, discord.User)):
            await self.show_user_info(ctx, result)
        else:
            await ctx.send(f'Nothing found for ID: `{check_id}`')

    @classmethod
    def time_since(cls, time: str):
        try:
            date_time = datetime.datetime.strptime(str(time), '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            time = f'{str(time)}.0'
            date_time = datetime.datetime.strptime(str(time), '%Y-%m-%d %H:%M:%S.%f')
        date_now = datetime.datetime.now(datetime.timezone.utc)
        date_now = date_now.replace(tzinfo=None)
        since_join = date_now - date_time

        mins, secs = divmod(int(since_join.total_seconds()), 60)
        hrs, mins = divmod(mins, 60)
        days, hrs = divmod(hrs, 24)
        mths, wks, days = cls.count_months(days)
        yrs, mths = divmod(mths, 12)

        m = f'{yrs}y {mths}m {wks}w {days}d {hrs}h {mins}min {secs}sec'
        m2 = [x for x in m.split() if x[0] != '0']
        s = ' '.join(m2[:2])
        resp = f'{s} ago' if s else 'Unknown'
        return resp

    @staticmethod
    def count_months(days: int):
        lens = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        cy = itertools.cycle(lens)
        months = 0
        m_temp = 0
        mo_len = next(cy)
        for i in range(1, days + 1):
            m_temp += 1
            if m_temp == mo_len:
                months += 1
                m_temp = 0
                mo_len = next(cy)
                if mo_len == 28 and months >= 48:
                    mo_len += 1

        weeks, days = divmod(m_temp, 7)
        return months, weeks, days

    @staticmethod
    def channel_type_emoji(channel):
        if getattr(channel, 'type', False):
            if str(channel.type) == 'text':
                return f'\U0001F4DD'  # {MEMO}
            elif str(channel.type) == 'voice':
                return f'\U0001F50A'  # :loud_sound:
            elif str(channel.type) == 'category':
                return f'\U0001F53B'  # :red_triangle_pointed_down:
            elif str(channel.type) == 'stage_voice':
                return f'\U0001F3A7'  # :headphones:
        return f'\U00002753'  # {BLACK QUESTION MARK ORNAMENT}
