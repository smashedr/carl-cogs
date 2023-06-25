import asyncio
import datetime
import discord
import itertools
import logging
from tabulate import tabulate
from typing import Optional, Union, Tuple

from redbot.core import commands
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as cf
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS, close_menu
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from .converters import CarlRoleConverter, CarlChannelConverter, FuzzyMember

log = logging.getLogger('red.botutils')

GuildChannel = Optional[Union[
    discord.TextChannel,
    discord.VoiceChannel,
    discord.CategoryChannel,
    discord.StageChannel,
    discord.ForumChannel,
]]


class Botutils(commands.Cog):
    """Carl's Botutils Cog"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self) -> None:
        log.info('%s: Cog Load', self.__cog_name__)

    async def cog_unload(self) -> None:
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.command(name='bitrateall')
    @commands.admin()
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def maxbitrateall(self, ctx, bitrate: int = 0):
        """Set the bitrate for ALL channels to Guild Max or <bitrate>."""
        await ctx.typing()
        limit = ctx.guild.bitrate_limit
        if bitrate and not (8000 > bitrate > 360000) or bitrate > limit:
            await ctx.send(f'Invalid bitrate. Specify a number between `8000` '
                           f'and `360000` or leave blank for the guild max of '
                           f'`{limit}`')
            return

        new_rate = bitrate or limit
        updated = []
        async with ctx.channel.typing():
            for channel in await AsyncIter(ctx.guild.voice_channels):
                if channel.bitrate != new_rate:
                    updated.append(channel.name)
                    reason = f'{ctx.author} used bitrateall {new_rate}'
                    await channel.edit(bitrate=new_rate, reason=reason)

        await ctx.send(f'Done. Updated: ```{updated or "Nothing"}```')

    @commands.command(name='moveusto', aliases=['moveus', 'moveall'])
    @commands.admin_or_permissions(move_members=True)
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def moveusto(self, ctx, *, channel: discord.VoiceChannel):
        """Moves all users from your current channel to <channel>"""
        await ctx.typing()
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send('You are not in a Voice channel.', delete_after=15)
            return

        source = ctx.author.voice.channel
        if channel == source:
            await ctx.send(f'You are already in the destination channel '
                           f'**{channel.name}**.', delete_after=15)
            return

        await ctx.send(f'Stand by, moving **{len(source.members)}** members '
                       f'to **{channel.name}**', delete_after=60)
        async with ctx.channel.typing():
            for member in await AsyncIter(source.members):
                await member.move_to(channel)
        await ctx.send('All done, enjoy =)', delete_after=60)

    @commands.command(name='roleaddmulti', aliases=['rolemulti'])
    @commands.admin()
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def roleaddmulti(self, ctx, role: discord.Role, *, members: str):
        """Attempts to add a <role> to multiple <users>, space separated..."""
        await ctx.typing()
        # if members:
        #     members = members.split()
        # else:
        #     members = ctx.guild.members
        members = members.split()
        log.debug(members)
        num_members = len(ctx.guild.members)
        message = await ctx.send(f'Will process **{len(members)}/{num_members}** '
                                 f'guild members for role `@{role.name}` \n'
                                 f'Minimum ETA **{num_members//5}** sec. '
                                 f'Proceed?')

        pred = ReactionPredicate.yes_or_no(message, ctx.author)
        start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            await self.bot.wait_for('reaction_add', check=pred, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send('Request timed out. Aborting.', delete_after=60)
            await message.delete()
            return

        if not pred.result:
            await ctx.send('Aborting...', delete_after=5)
            await message.delete()
            return

        await ctx.send('Processing now. Please wait...')
        users = []
        async with ctx.channel.typing():
            for member in await AsyncIter(ctx.guild.members, delay=1, steps=5):
                for m in await AsyncIter(members):
                    if (member.name and m.lower() == member.name.lower()) or \
                            (member.nick and m.lower() == member.nick.lower()):
                        if role not in member.roles:
                            await member.add_roles(role, reason=f'{ctx.author} roleaddmulti')
                            users.append(member.name)
        await ctx.send(f'Done! Added @{role.mention} to:\n{users}')
        await message.delete()

    # Guild, Emoji, Role, Channel, User ID

    @commands.command(name='guildid', aliases=['gid', 'sid', 'serverid'])
    @commands.guild_only()
    async def guild_id(self, ctx):
        """Get the ID for the guild."""
        await ctx.typing()
        await ctx.send(f'\U0000269C **{ctx.guild.name}** ID: `{ctx.guild.id}`')

    @commands.command(name='emojiid', aliases=['eid'])
    @commands.guild_only()
    async def emoji_id(self, ctx, emoji: discord.Emoji):
        """Get the ID for an <emoji>."""
        await ctx.typing()
        await ctx.send(f'**{emoji}** ID: `{emoji.id}`')

    @commands.command(name='roleid', aliases=['rid'])
    @commands.guild_only()
    async def role_id(self, ctx, *, role: Union[CarlRoleConverter, discord.Role]):
        """Get the ID for a <role>."""
        await ctx.typing()
        await ctx.send(f'{role.mention} ID: `{role.id}`')

    @commands.command(name='channelid', aliases=['cid'])
    @commands.guild_only()
    async def channel_id(self, ctx, *,
                         channel: Optional[Union[CarlChannelConverter, GuildChannel]]):
        """Get the ID for a <channel>."""
        await ctx.typing()
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
        await ctx.typing()
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

    # Emoji Info

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

    # Guild Info

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

    async def show_guild_info(self, ctx, guild: discord.Guild):
        msg = await ctx.send('**Guild**```\nLoading guild info...```')
        embed = await self.guild_embed(guild)
        await msg.edit(content='**Guild**', embed=embed)

    # Role Info

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
        em.set_thumbnail(url=role.guild.icon.url)
        await msg.edit(embed=em)

    # User Info

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

        all_guilds = [member.guild.name for member in self.bot.get_all_members() if member.id == user.id]
        shared_guilds = str(len(set(all_guilds)))
        # if user.is_avatar_animated():
        #     icon_url = user.avatar_url_as(format='gif')
        # else:
        #     icon_url = user.avatar_url_as(format='png')

        # em = discord.Embed()
        # em.colour = user.color
        # em.set_thumbnail(url=user.avatar_url)
        # em.set_author(name=str(user), url=ctx.message.jump_url)
        # em.title = user.display_name
        # em.description = f'Discord Member for {self.time_since(user.created_at)}'
        # em.add_field(name='Invoker', value=ctx.author.mention)
        # em.set_footer(text=f'ID: {ctx.author.id}', icon_url=ctx.author.avatar_url)
        # em.timestamp = ctx.message.created_at

        data = '**User**```ini\n'
        data += '[Name]:          {}\n'.format(cf.escape(str(user)))
        data += '[ID]:            {}\n'.format(user.id)
        data += '[Created]:       {}\n'.format(self.time_since(user.created_at))
        data += '[Servers]:       {} shared\n'.format(len(shared_guilds))
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
        data += '[Avatar URL]:\n{}\n'.format(user.avatar.url)
        data += '```'

        await msg.edit(content=data)

    # Channel Info

    @commands.command(name='channelinfo', aliases=['cinfo', 'chinfo'])
    @commands.guild_only()
    async def channel_info(self, ctx, *, channel: CarlChannelConverter = None):
        """Shows channel information. Defaults to current text channel."""
        channel = channel or ctx.channel
        await self.show_channel_info(ctx, channel)

    @classmethod
    async def show_channel_info(cls, ctx,
                                channel: GuildChannel):
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

    # ID Resolver

    @commands.command(name='idinfo', aliases=['id', 'getid'])
    @commands.guild_only()
    async def id_info(self, ctx, check_id: int):
        """Resolve any ID to a Channel, Emoji, Guild, Role or User."""
        await ctx.typing()
        result = None
        if ctx.guild.id == check_id:
            result = ctx.guild
        elif ctx.channel.id == check_id:
            result = ctx.channel
        elif ctx.author.id == check_id:
            result = ctx.author

        log.debug(0)
        if not result:
            check_local = (list(ctx.guild.roles) + list(ctx.guild.emojis) + list(ctx.guild.members) + list(ctx.guild.channels))

            result = discord.utils.get(check_local, id=check_id)

        log.debug(1)
        if not result:
            roles = [g.roles for g in self.bot.guilds]
            check_all = (
                    self.bot.guilds + self.bot.emojis
                    + list(itertools.chain.from_iterable(roles))
                    + [m for m in self.bot.get_all_members()]
                    + [c for c in self.bot.get_all_channels()]
            )
            result = discord.utils.get(check_all, id=check_id)

        log.debug(2)
        if isinstance(result, discord.Emoji):
            await ctx.invoke(self.emoji_info, result)
        elif isinstance(result, discord.Guild):
            await self.show_guild_info(ctx, result)
        elif isinstance(result, discord.Role):
            await self.show_role_info(ctx, result)
        elif isinstance(result, GuildChannel):
            await self.show_channel_info(ctx, result)
        elif isinstance(result, (discord.Member, discord.User)):
            await self.show_user_info(ctx, result)
        else:
            await ctx.send(f'Nothing found for ID: `{check_id}`')

    # Helper Functions

    @classmethod
    def time_since(cls, date_time: Union[str, datetime.datetime]):
        log.debug(type(date_time))
        log.debug(str(date_time))
        if not isinstance(date_time, datetime.datetime):
            try:
                log.debug(str(date_time))
                date_time = datetime.datetime.strptime(str(date_time), '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                stime = f'{str(date_time)}.0'
                log.debug(str(stime))
                date_time = datetime.datetime.strptime(str(stime), '%Y-%m-%d %H:%M:%S.%f')
        date_now = datetime.datetime.now(datetime.timezone.utc)
        # date_now = date_now.replace(tzinfo=None)
        log.debug(type(date_now))
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
    def count_months(days: int) -> Tuple[int, int, int]:
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
    def channel_type_emoji(channel: discord.abc.GuildChannel) -> str:
        if getattr(channel, 'type', False):
            if str(channel.type) == 'text':
                return f'\U0001F4AC'  # {SPEECH BALLOON}
            elif str(channel.type) == 'voice':
                return f'\U0001F50A'  # :loud_sound:
            elif str(channel.type) == 'category':
                return f'\U0001F53B'  # :red_triangle_pointed_down:
            elif str(channel.type) == 'stage_voice':
                return f'\U0001F3A7'  # :headphones:
        return f'\U00002753'  # {BLACK QUESTION MARK ORNAMENT}

    async def guild_embed(self, guild: discord.Guild) -> discord.Embed:
        """Builds a guild embed."""

        def _size(number: Union[int, float]) -> str:
            for unit in ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]:
                if abs(number) < 1024.0:
                    return "{0:.1f}{1}".format(number, unit)
                number /= 1024.0
            return "{0:.1f}{1}".format(number, "YB")

        def _bitsize(number: Union[int, float]) -> str:
            for unit in ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]:
                if abs(number) < 1000.0:
                    return "{0:.1f}{1}".format(number, unit)
                number /= 1000.0
            return "{0:.1f}{1}".format(number, "YB")

        created_at = "Created on {date}. That's over {num}!".format(
            date=f"<t:{int(guild.created_at.replace(tzinfo=datetime.timezone.utc).timestamp())}:D>",
            num=f"<t:{int(guild.created_at.replace(tzinfo=datetime.timezone.utc).timestamp())}:R>",
        )
        total_users = guild.member_count
        try:
            joined_at = guild.me.joined_at
        except AttributeError:
            joined_at = datetime.datetime.utcnow()
        bot_joined = f"<t:{int(joined_at.replace(tzinfo=datetime.timezone.utc).timestamp())}:D>"
        since_joined = f"<t:{int(joined_at.replace(tzinfo=datetime.timezone.utc).timestamp())}:R>"
        joined_on = (
            "{bot} joined this server on **{bot_join}**.\n"
            "That's over **{since_join}**!"
        ).format(
            bot=self.bot.user.mention,
            bot_join=bot_joined,
            since_join=since_joined,
        )
        shard = (
            "\nShard ID: **{shard_id}/{shard_count}**".format(
                shard_id=guild.shard_id + 1,
                shard_count=self.bot.shard_count,
            )
            if self.bot.shard_count > 1
            else ""
        )
        colour = guild.roles[-1].colour

        member_msg = "Total Users: **{}**\n".format(total_users)
        online_stats = {
            "Humans: ": lambda x: not x.bot,
            " • Bots: ": lambda x: x.bot,
            "\N{LARGE GREEN CIRCLE}": lambda x: x.status is discord.Status.online,
            "\N{LARGE ORANGE CIRCLE}": lambda x: x.status is discord.Status.idle,
            "\N{LARGE RED CIRCLE}": lambda x: x.status is discord.Status.do_not_disturb,
            "\N{MEDIUM WHITE CIRCLE}": lambda x: x.status is discord.Status.offline,
            "\N{LARGE PURPLE CIRCLE}": lambda x: (
                    x.activity is not None and x.activity.type is discord.ActivityType.streaming
            ),
        }
        count = 1
        for emoji, value in online_stats.items():
            try:
                num = len([m for m in guild.members if value(m)])
            except Exception as error:
                print(error)
                continue
            else:
                member_msg += f"{emoji} **{num}** " + (
                    "\n" if count % 2 == 0 else ""
                )
            count += 1

        text_channels = len(guild.text_channels)
        nsfw_channels = len([c for c in guild.text_channels if c.is_nsfw()])
        voice_channels = len(guild.voice_channels)

        verif = {
            "none": "0 - None",
            "low": "1 - Low",
            "medium": "2 - Medium",
            "high": "3 - High",
            "extreme": "4 - Extreme",
        }

        features = {
            "ANIMATED_ICON": "Animated Icon",
            "BANNER": "Banner Image",
            "COMMERCE": "Commerce",
            "COMMUNITY": "Community",
            "DISCOVERABLE": "Server Discovery",
            "FEATURABLE": "Featurable",
            "INVITE_SPLASH": "Splash Invite",
            "MEMBER_LIST_DISABLED": "Member list disabled",
            "MEMBER_VERIFICATION_GATE_ENABLED": "Membership Screening enabled",
            "MORE_EMOJI": "More Emojis",
            "NEWS": "News Channels",
            "PARTNERED": "Partnered",
            "PREVIEW_ENABLED": "Preview enabled",
            "PUBLIC_DISABLED": "Public disabled",
            "VANITY_URL": "Vanity URL",
            "VERIFIED": "Verified",
            "VIP_REGIONS": "VIP Voice Servers",
            "WELCOME_SCREEN_ENABLED": "Welcome Screen enabled",
        }
        guild_features_list = [
            f"✅ {name}" for feature, name in features.items() if feature in guild.features
        ]

        em = discord.Embed(
            description=(f"{guild.description}\n\n" if guild.description else ""
                         f"{created_at}\n{joined_on}"),
            colour=colour,
        )
        em.set_author(
            name=guild.name,
            icon_url="https://cdn.discordapp.com/emojis/457879292152381443.png"
            if "VERIFIED" in guild.features
            else "https://cdn.discordapp.com/emojis/508929941610430464.png"
            if "PARTNERED" in guild.features
            else None,
            url=guild.icon.url
            if guild.icon.url
            else "https://cdn.discordapp.com/embed/avatars/1.png",
        )
        em.set_thumbnail(
            url=guild.icon.url
            if guild.icon.url
            else "https://cdn.discordapp.com/embed/avatars/1.png"
        )
        em.add_field(name="Members:", value=member_msg)
        em.add_field(
            name="Channels:",
            value=(
                "\N{SPEECH BALLOON} Text: **{text}**\n{nsfw}"
                "\N{SPEAKER WITH THREE SOUND WAVES} Voice: {voice}"
            ).format(
                text=text_channels,
                nsfw="\N{NO ONE UNDER EIGHTEEN SYMBOL} Nsfw: {}\n".format(
                    nsfw_channels
                )
                if nsfw_channels
                else "",
                voice=voice_channels,
            ),
        )
        owner = guild.owner if guild.owner else await self.bot.get_or_fetch_user(guild.owner_id)
        em.add_field(
            name="Utility:",
            value=(
                "Owner: {owner_mention}\n"
                "{owner}\n"
                "Level: **{verif}**\n"
                "ID: **{id}{shard}**"
            ).format(
                owner_mention=str(owner.mention),
                owner=str(owner),
                verif=verif[str(guild.verification_level)],
                id=str(guild.id),
                shard=shard,
            ),
            inline=False,
        )
        em.add_field(
            name="Misc:",
            value=(
                "AFK channel: **{afk_chan}**\n"
                "AFK timeout: **{afk_timeout}**\n"
                "Custom emojis: **{emojis}**\n"
                "Roles: **{roles}**"
            ).format(
                afk_chan=str(guild.afk_channel) if guild.afk_channel else "Not set",
                afk_timeout=guild.afk_timeout,
                emojis=len(guild.emojis),
                roles=len(guild.roles),
            ),
            inline=False,
        )
        if guild_features_list:
            em.add_field(name="Server features:", value="\n".join(guild_features_list))
        if guild.premium_tier != 0:
            nitro_boost = (
                "Tier **{boostlevel}** with **{nitroboosters}** boosters\n"
                "File size limit: **{filelimit}**\n"
                "Emoji limit: **{emojis_limit}**\n"
                "VCs max bitrate: **{bitrate}**"
            ).format(
                boostlevel=str(guild.premium_tier),
                nitroboosters=guild.premium_subscription_count,
                filelimit=_size(guild.filesize_limit),
                emojis_limit=str(guild.emoji_limit),
                bitrate=_bitsize(guild.bitrate_limit),
            )
            em.add_field(name="Nitro Boost:", value=nitro_boost)
        if guild.splash:
            em.set_image(url=guild.splash.url)
        return em
