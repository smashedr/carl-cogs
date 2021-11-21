import asyncio
import datetime
import discord
import inspect
import itertools
import logging
import re

from contextlib import suppress as sps
from tabulate import tabulate
from typing import Optional, Union

from redbot.core import checks, commands
from redbot.core.utils import chat_formatting as cf
from redbot.core.utils.common_filters import filter_invites
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS, close_menu

from .converters import ChannelConverter, FuzzyMember


logger = logging.getLogger('red.utils')


class Utils(commands.Cog):
    """Carl's Utils Cog"""
    def __init__(self, bot):
        self.bot = bot

    async def initialize(self) -> None:
        logger.info('Initializing Carlcog Cog')

    def cog_unload(self):
        logger.info('Unload Carlcog Cog')

    @commands.group(name='access')
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def access(self, ctx):
        """Check channel access"""
        pass

    @access.command(name='compare')
    async def compare(self, ctx, user: discord.Member, guild: int = None):
        """Compare channel access with [user]."""
        if user is None:
            return
        if guild is None:
            guild = ctx.guild
        else:
            guild = self.bot.get_guild(guild)

        try:
            tcs = guild.text_channels
            vcs = guild.voice_channels
        except AttributeError:
            return await ctx.send("User is not in that guild or I do not have access to that guild.")

        author_text_channels = [c for c in tcs if c.permissions_for(ctx.author).read_messages is True]
        author_voice_channels = [c for c in vcs if c.permissions_for(ctx.author).connect is True]

        user_text_channels = [c for c in tcs if c.permissions_for(user).read_messages is True]
        user_voice_channels = [c for c in vcs if c.permissions_for(user).connect is True]

        author_only_t = set(author_text_channels) - set(
            user_text_channels
        )  # text channels only the author has access to
        author_only_v = set(author_voice_channels) - set(
            user_voice_channels
        )  # voice channels only the author has access to

        user_only_t = set(user_text_channels) - set(author_text_channels)  # text channels only the user has access to
        user_only_v = set(user_voice_channels) - set(
            author_voice_channels
        )  # voice channels only the user has access to

        common_t = list(
            set([c for c in tcs]) - author_only_t - user_only_t
        )  # text channels that author and user have in common
        common_v = list(
            set([c for c in vcs]) - author_only_v - user_only_v
        )  # voice channels that author and user have in common

        msg = "```ini\n"
        msg += "{} [TEXT CHANNELS IN COMMON]:\n\n{}\n\n".format(len(common_t), ", ".join([c.name for c in common_t]))
        msg += "{} [TEXT CHANNELS {} HAS EXCLUSIVE ACCESS TO]:\n\n{}\n\n".format(
            len(user_only_t), user.name.upper(), ", ".join([c.name for c in user_only_t])
        )
        msg += "{} [TEXT CHANNELS YOU HAVE EXCLUSIVE ACCESS TO]:\n\n{}\n\n\n".format(
            len(author_only_t), ", ".join([c.name for c in author_only_t])
        )
        msg += "{} [VOICE CHANNELS IN COMMON]:\n\n{}\n\n".format(len(common_v), ", ".join([c.name for c in common_v]))
        msg += "{} [VOICE CHANNELS {} HAS EXCLUSIVE ACCESS TO]:\n\n{}\n\n".format(
            len(user_only_v), user.name.upper(), ", ".join([c.name for c in user_only_v])
        )
        msg += "{} [VOICE CHANNELS YOU HAVE EXCLUSIVE ACCESS TO]:\n\n{}\n\n".format(
            len(author_only_v), ", ".join([c.name for c in author_only_v])
        )
        msg += "```"
        for page in cf.pagify(msg, delims=["\n"], shorten_by=16):
            await ctx.send(page)

    @access.command(name='text')
    async def text(self, ctx, user: discord.Member = None, guild: int = None):
        """Check text channel access."""
        if user is None:
            user = ctx.author
        if guild is None:
            guild = ctx.guild
        else:
            guild = self.bot.get_guild(guild)

        try:
            can_access = [c.name for c in guild.text_channels if c.permissions_for(user).read_messages == True]
            text_channels = [c.name for c in guild.text_channels]
        except AttributeError:
            return await ctx.send("User is not in that guild or I do not have access to that guild.")

        prefix = "You have" if user.id == ctx.author.id else user.name + " has"
        msg = "```ini\n[{} access to {} out of {} text channels]\n\n".format(
            prefix, len(can_access), len(text_channels)
        )

        msg += "[ACCESS]:\n{}\n\n".format(", ".join(can_access))
        msg += "[NO ACCESS]:\n{}\n```".format(", ".join(list(set(text_channels) - set(can_access))))
        for page in cf.pagify(msg, delims=["\n"], shorten_by=16):
            await ctx.send(page)

    @access.command(name='voice')
    async def voice(self, ctx, user: discord.Member = None, guild: int = None):
        """Check voice channel access."""
        if user is None:
            user = ctx.author
        if guild is None:
            guild = ctx.guild
        else:
            guild = self.bot.get_guild(guild)

        try:
            can_access = [c.name for c in guild.voice_channels if c.permissions_for(user).connect is True]
            voice_channels = [c.name for c in guild.voice_channels]
        except AttributeError:
            return await ctx.send("User is not in that guild or I do not have access to that guild.")

        prefix = "You have" if user.id == ctx.author.id else user.name + " has"
        msg = "```ini\n[{} access to {} out of {} voice channels]\n\n".format(
            prefix, len(can_access), len(voice_channels)
        )

        msg += "[ACCESS]:\n{}\n\n".format(", ".join(can_access))
        msg += "[NO ACCESS]:\n{}\n```".format(", ".join(list(set(voice_channels) - set(can_access))))
        for page in cf.pagify(msg, delims=["\n"], shorten_by=16):
            await ctx.send(page)

    @commands.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def banlist(self, ctx):
        """Displays the server's banlist."""
        try:
            banlist = await ctx.guild.bans()
        except discord.errors.Forbidden:
            await ctx.send("I do not have the `Ban Members` permission.")
            return
        bancount = len(banlist)
        ban_list = []
        if bancount == 0:
            msg = "No users are banned from this server."
        else:
            msg = ""
            for user_obj in banlist:
                user_name = f"{user_obj.user.name}#{user_obj.user.discriminator}"
                msg += f"`{user_obj.user.id} - {user_name}`\n"

        banlist = sorted(msg)
        embed_list = []
        for page in cf.pagify(msg, shorten_by=1400):
            embed = discord.Embed(
                description="**Total bans:** {}\n\n{}".format(bancount, page),
                colour=await ctx.embed_colour(),
            )
            embed_list.append(embed)
        await menu(ctx, embed_list, DEFAULT_CONTROLS)

    @commands.command(name='cid')
    @commands.guild_only()
    async def cid(self, ctx):
        """Shows the channel ID."""
        await ctx.send("**#{0.name} ID:** {0.id}".format(ctx.channel))

    @commands.command(name='channelinfo', aliases=['cinfo', 'chinfo'])
    @commands.guild_only()
    async def channelinfo(self, ctx, channel: ChannelConverter = None):
        """Shows channel information. Defaults to current text channel."""
        channel = channel or ctx.channel
        logger.debug(channel)

        yesno = {True: "Yes", False: "No"}
        typemap = {
            discord.TextChannel: "Text Channel",
            discord.VoiceChannel: "Voice Channel",
            discord.CategoryChannel: "Category",
        }

        load = "**Channel**```\nLoading channel info...```"
        waiting = await ctx.send(load)

        with sps(Exception):
            caller = inspect.currentframe().f_back.f_code.co_name.strip()

        ch_type = typemap[type(channel)]
        data = f"**Channel: {ch_type}**```ini\n"
        if caller == "invoke" or channel.guild != ctx.guild:
            data += "[Server]:     {}\n".format(channel.guild.name)
        data += "[Name]:       {}\n".format(cf.escape(str(channel)))
        data += "[ID]:         {}\n".format(channel.id)
        data += "[Private]:    {}\n".format(yesno[isinstance(channel, discord.abc.PrivateChannel)])
        if isinstance(channel, discord.TextChannel) and channel.topic != "":
            data += "[Topic]:      {}\n".format(channel.topic)
        data += "[Position]:   {}\n".format(channel.position)
        data += "[Created]:    {}\n".format(self._dynamic_time(channel.created_at))
        data += "[Type]:       {}\n".format(ch_type)
        if isinstance(channel, discord.VoiceChannel):
            data += "[Users]:      {}\n".format(len(channel.members))
            data += "[User limit]: {}\n".format(channel.user_limit)
            data += "[Bitrate]:    {}kbps\n".format(int(channel.bitrate / 1000))
        data += "```"
        await waiting.edit(content=data)

    @commands.command(name="emojiid", aliases=["eid"])
    @commands.guild_only()
    async def emojiid(self, ctx, emoji: discord.Emoji):
        """Get an id for an emoji."""
        await ctx.send(f"**ID for {emoji}:**   {emoji.id}")

    @commands.command(name='emojiinfo', aliases=['einfo'])
    @commands.guild_only()
    async def emojiinfo(self, ctx, emoji: discord.Emoji):
        """Shows Emoji information for <emoji>."""
        message = (
            f"{str(emoji)}\n"
            f"```ini\n"
            f"[NAME]:       {emoji.name}\n"
            f"[GUILD]:      {emoji.guild}\n"
            f"[URL]:        {emoji.url}\n"
            f"[ANIMATED]:   {emoji.animated}"
            "```"
        )
        await ctx.send(message)

    # @commands.command(name='inrole')
    # @commands.guild_only()
    # @checks.mod_or_permissions(manage_guild=True)
    # async def inrole(self, ctx, *, rolename):
    #     """Check members in the specified <rolename>."""
    #     guild = ctx.guild
    #     await ctx.trigger_typing()
    #     if rolename.startswith("<@&"):
    #         role_id = int(re.search(r"<@&(.{18})>$", rolename)[1])
    #         role = discord.utils.get(ctx.guild.roles, id=role_id)
    #     elif len(rolename) in [17, 18] and rolename.isdigit():
    #         role = discord.utils.get(ctx.guild.roles, id=int(rolename))
    #     else:
    #         role = discord.utils.find(lambda r: r.name.lower() == rolename.lower(), guild.roles)
    #
    #     if not role:
    #         roles = []
    #         for r in guild.roles:
    #             if rolename.lower() in r.name.lower():
    #                 roles.append(r)
    #         if not roles:
    #             await ctx.send("No roles were found.")
    #             return
    #
    #         msg = (
    #             f"**{len(roles)} roles found with** `{rolename}` **in the name.**\n"
    #             f"Type the number of the role you wish to see.\n\n"
    #         )
    #         tbul8 = []
    #         for num, role in enumerate(roles):
    #             tbul8.append([num + 1, role.name])
    #         m1 = await ctx.send(msg + tabulate(tbul8, tablefmt="plain"))
    #
    #         def check(m):
    #             if (m.author == ctx.author) and (m.channel == ctx.channel):
    #                 return True
    #
    #         try:
    #             response = await self.bot.wait_for("message", check=check, timeout=25)
    #         except asyncio.TimeoutError:
    #             await m1.delete()
    #             return
    #         if not response.content.isdigit():
    #             await m1.delete()
    #             return
    #         else:
    #             response = int(response.content)
    #
    #         if response not in range(0, len(roles) + 1):
    #             return await ctx.send("Cancelled.")
    #         elif response == 0:
    #             return await ctx.send("Cancelled.")
    #         else:
    #             role = roles[response - 1]
    #
    #     awaiter = await ctx.send(
    #         embed=discord.Embed(description="Getting member names...", colour=await ctx.embed_colour())
    #     )
    #     users_in_role = "\n".join(sorted(m.display_name for m in guild.members if role in m.roles))
    #     if len(users_in_role) == 0:
    #         embed = discord.Embed(
    #             description=cf.bold(f"0 users found in the {role.name} role."),
    #             colour=await ctx.embed_colour(),
    #         )
    #         await awaiter.edit(embed=embed)
    #         return
    #     try:
    #         await awaiter.delete()
    #     except discord.NotFound:
    #         pass
    #     embed_list = []
    #     for page in cf.pagify(users_in_role, delims=["\n"], page_length=200):
    #         embed = discord.Embed(
    #             description=cf.bold("{1} users found in the {0} role.\n").format(
    #                 role.name, len([m for m in guild.members if role in m.roles])
    #             ),
    #             colour=await ctx.embed_colour(),
    #         )
    #         embed.add_field(name="Users", value=page)
    #         embed_list.append(embed)
    #     final_embed_list = []
    #     for i, embed in enumerate(embed_list):
    #         embed.set_footer(text=f"Page {i + 1}/{len(embed_list)}")
    #         final_embed_list.append(embed)
    #     if len(embed_list) == 1:
    #         close_control = {"\N{CROSS MARK}": close_menu}
    #         await menu(ctx, final_embed_list, close_control)
    #     else:
    #         await menu(ctx, final_embed_list, DEFAULT_CONTROLS)

    @commands.command(name='joined')
    @commands.guild_only()
    async def joined(self, ctx, user: discord.Member = None):
        """Show when a <user> joined the guild."""
        await ctx.trigger_typing()
        user = user or ctx.author
        if user.joined_at:
            user_joined = user.joined_at.strftime("%d %b %Y %H:%M")
            since_joined = (ctx.message.created_at - user.joined_at).days
            joined_on = f"{user_joined} ({since_joined} days ago)"
        else:
            joined_on = "a mysterious date that not even Discord knows."

        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            embed = discord.Embed(
                description=f"{user.mention} joined this guild on {joined_on}.",
                color=await ctx.embed_colour(),
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"{user.display_name} joined this guild on {joined_on}.")

    @commands.command(name='listguilds', aliases=['listservers'])
    @checks.is_owner()
    async def listguilds(self, ctx):
        """List the guilds|servers the bot is in."""
        await ctx.trigger_typing()
        asciidoc = lambda m: "```asciidoc\n{}\n```".format(m)
        guilds = sorted(self.bot.guilds, key=lambda g: -g.member_count)
        header = ("```\n" "The bot is in the following {} server{}:\n" "```").format(
            len(guilds), "s" if len(guilds) > 1 else ""
        )

        max_zpadding = max([len(str(g.member_count)) for g in guilds])
        form = "{gid} :: {mems:0{zpadding}} :: {name}"
        all_forms = [
            form.format(gid=g.id, mems=g.member_count, name=filter_invites(cf.escape(g.name)), zpadding=max_zpadding)
            for g in guilds
        ]
        final = "\n".join(all_forms)

        await ctx.send(header)
        page_list = []
        for page in cf.pagify(final, delims=["\n"], page_length=1000):
            page_list.append(asciidoc(page))

        if len(page_list) == 1:
            return await ctx.send(asciidoc(page))
        await menu(ctx, page_list, DEFAULT_CONTROLS)

    @commands.command(name='listchannel', aliases=['listch', 'listchannels'])
    @commands.guild_only()
    @checks.admin()
    async def listchannel(self, ctx):
        """List the channels of the current server."""
        await ctx.trigger_typing()
        asciidoc = lambda m: "```asciidoc\n{}\n```".format(m)
        channels = ctx.guild.channels
        top_channels, category_channels = self.sort_channels(ctx.guild.channels)
        topChannels_formed = "\n".join(self.channels_format(top_channels))
        categories_formed = "\n\n".join([self.category_format(tup) for tup in category_channels])

        await ctx.send(f"{ctx.guild.name} has {len(channels)} channel{'s' if len(channels) > 1 else ''}.")

        for page in cf.pagify(topChannels_formed, delims=["\n"], shorten_by=16):
            await ctx.send(asciidoc(page))

        for page in cf.pagify(categories_formed, delims=["\n\n"], shorten_by=16):
            await ctx.send(asciidoc(page))

    @commands.command(name="newusers", aliases=["recentusers"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def newusers(self, ctx, count: int = 5, fm: str = "py"):
        """Lists the newest 5 members."""
        await ctx.trigger_typing()
        guild = ctx.guild
        count = max(min(count, 25), 5)
        members = sorted(guild.members, key=lambda m: m.joined_at, reverse=True)[:count]

        head1 = "{} newest members".format(count)
        header = "{:>33}\n{}\n\n".format(head1, "-" * 57)

        user_body = (
            " {mem} ({memid})\n"
            " {spcs}Joined Guild:    {sp1}{join}\n"
            " {spcs}Account Created: {sp2}{created}\n\n"
        )

        spcs = [" " * (len(m.name) // 2) for m in members]
        smspc = min(spcs, key=lambda it: len(it))

        for member in members:
            req = self.calculate_diff(member.joined_at, member.created_at)
            sp1 = req[0] if req[1] == 0 else 0
            sp2 = req[0] if req[1] == 1 else 0

            header += user_body.format(
                mem=member.display_name,
                memid=member.id,
                join=self._dynamic_time(member.joined_at),
                created=self._dynamic_time(member.created_at),
                spcs=smspc,
                sp1="0" * sp1,
                sp2="0" * sp2,
            )

        for page in cf.pagify(header, delims=["\n\n"]):
            await ctx.send(cf.box(page, lang=fm))

    @commands.command(name="perms", aliases=["perm"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def perms(self, ctx, user: discord.Member = None):
        """Fetch a specific <user> permissions."""
        await ctx.trigger_typing()
        user = user or ctx.author
        perms = iter(ctx.channel.permissions_for(user))
        perms_we_have = ""
        perms_we_dont = ""
        for x in sorted(perms):
            if "True" in str(x):
                perms_we_have += "+\t{0}\n".format(str(x).split("'")[1])
            else:
                perms_we_dont += "-\t{0}\n".format(str(x).split("'")[1])
        await ctx.send(cf.box("{0}{1}".format(perms_we_have, perms_we_dont), lang="diff"))

    @commands.command(name="roleid", aliases=["rid"])
    @commands.guild_only()
    async def roleid(self, ctx, *, rolename):
        """Shows the id of a <rolename>."""
        await ctx.trigger_typing()
        if rolename is discord.Role:
            role = rolename
        else:
            role = self._role_from_string(ctx.guild, rolename)
        if role is None:
            await ctx.send(embed=discord.Embed(description="Cannot find role.", colour=await ctx.embed_colour()))
            return
        await ctx.send(f"**{rolename} ID:** {role.id}")

    @commands.guild_only()
    @commands.command(name='roleinfo', aliases=['rinfo'])
    async def roleinfo(self, ctx, role: discord.Role):
        """Shows role info for <role>."""
        msg = discord.Embed(description="Gathering role stats...", colour=role.color)
        loadingmsg = await ctx.send('**Role**', embed=msg)

        caller = inspect.currentframe().f_back.f_code.co_name

        perms = iter(role.permissions)
        perms_we_have = ""
        perms_we_dont = ""
        for x in sorted(perms):
            if "True" in str(x):
                perms_we_have += "{0}\n".format(str(x).split("'")[1])
            else:
                perms_we_dont += "{0}\n".format(str(x).split("'")[1])

        em = discord.Embed(colour=role.colour)
        if caller == "invoke":
            em.add_field(name="Server", value=role.guild.name)
        em.add_field(name="Role Name", value=role.name)
        em.add_field(name="Created", value=self._dynamic_time(role.created_at))
        em.add_field(name="Users in Role", value=len([m for m in role.guild.members if role in m.roles]))
        em.add_field(name="ID", value=role.id)
        em.add_field(name="Color", value=role.color)
        em.add_field(name="Position", value=role.position)
        em.add_field(name="Valid Permissions", value="{}".format(perms_we_have or 'None'))
        em.add_field(name="Invalid Permissions", value="{}".format(perms_we_dont or 'None'))
        em.set_thumbnail(url=role.guild.icon_url)
        await loadingmsg.edit(embed=em)

    @commands.command(name='rolelist', aliases=["listroles"])
    @commands.guild_only()
    @checks.admin()
    async def rolelist(self, ctx):
        """Displays the server's roles."""
        await ctx.trigger_typing()
        form = "`{rpos:0{zpadding}}` - `{rid}` - `{rcolor}` - {rment} "
        max_zpadding = max([len(str(r.position)) for r in ctx.guild.roles])
        role_list = [
            form.format(rpos=r.position, zpadding=max_zpadding, rid=r.id, rment=r.mention, rcolor=r.color)
            for r in ctx.guild.roles
        ]

        role_list = sorted(role_list, reverse=True)
        role_list = "\n".join(role_list)
        embed_list = []
        for page in cf.pagify(role_list, shorten_by=1400):
            embed = discord.Embed(
                description=f"**Total roles:** {len(ctx.guild.roles)}\n\n{page}",
                colour=await ctx.embed_colour(),
            )
            embed_list.append(embed)
        await menu(ctx, embed_list, DEFAULT_CONTROLS)

    @commands.command(name='sharedservers', hidden=True)
    async def sharedservers(self, ctx, user: discord.Member = None):
        """Shows shared server info. Defaults to author."""
        user = user or ctx.author
        await ctx.trigger_typing()

        mutual_guilds = user.mutual_guilds
        data = f"[Guilds]:     {len(mutual_guilds)} shared\n"
        shared_servers = sorted([g.name for g in mutual_guilds], key=lambda v: (v.upper(), v[0].islower()))
        data += f"[In Guilds]:  {cf.humanize_list(shared_servers, style='unit')}"

        for _ in cf.pagify(data, ["\n"], page_length=1800):
            await ctx.send(f"```ini\n{data}```")

    @commands.command(name='guildid', aliases=['gid', 'sid', 'serverid'])
    @commands.guild_only()
    async def guildid(self, ctx):
        """Show the guild ID."""
        await ctx.trigger_typing()
        await ctx.send("**{0.name} ID:** {0.id}".format(ctx.guild))

    @commands.command(name='guildinfo', aliases=['ginfo', 'sinfo', 'serverinfo'])
    @commands.guild_only()
    async def guildinfo(self, ctx, guild: discord.Guild = None):
        """Shows information for the <guild>."""
        guild = guild or ctx.guild

        load = "**Guild**```\nLoading guild info...```"
        waiting = await ctx.send(load)

        online = str(len([m.status for m in guild.members if str(m.status) == "online" or str(m.status) == "idle"]))
        total_users = str(len(guild.members))
        text_channels = [x for x in guild.channels if isinstance(x, discord.TextChannel)]
        voice_channels = [x for x in guild.channels if isinstance(x, discord.VoiceChannel)]

        data = "**Guild**```ini\n"
        data += "[Name]:     {}\n".format(guild.name)
        data += "[ID]:       {}\n".format(guild.id)
        data += "[Region]:   {}\n".format(guild.region)
        data += "[Owner]:    {}\n".format(guild.owner)
        data += "[Users]:    {}/{}\n".format(online, total_users)
        data += "[Text]:     {} channels\n".format(len(text_channels))
        data += "[Voice]:    {} channels\n".format(len(voice_channels))
        data += "[Emojis]:   {}\n".format(len(guild.emojis))
        data += "[Roles]:    {} \n".format(len(guild.roles))
        data += "[Created]:  {}\n```".format(self._dynamic_time(guild.created_at))
        await waiting.edit(content=data)

    @commands.command(name="userid", aliases=["uid"])
    @commands.guild_only()
    async def userid(self, ctx, partial_name_or_nick: Optional[FuzzyMember]):
        """Search for user ids from a fuzzy name search."""
        partial_name_or_nick = partial_name_or_nick or ctx.author
        await ctx.trigger_typing()

        table = [["ID", "Name", "#", "Display Name"]]
        for user in partial_name_or_nick:
            table.append([user.id, user.name, user.discriminator, user.display_name])
        msg = tabulate(table, headers='firstrow')

        pages = []
        for page in cf.pagify(msg, delims=["\n"], page_length=1800):
            pages.append(cf.box(page))

        if len(pages) == 1:
            close_control = {"\N{CROSS MARK}": close_menu}
            await menu(ctx, pages, close_control)
        else:
            await menu(ctx, pages, DEFAULT_CONTROLS)

    @commands.command(name='userinfo', aliases=['uinfo'])
    @commands.guild_only()
    async def userinfo(self, ctx, user: discord.Member = None):
        """Shows information on <user>. Defaults to author."""
        user = user or ctx.author

        load = "**User**```\nLoading user info...```"
        waiting = await ctx.send(load)

        caller = inspect.currentframe().f_back.f_code.co_name

        roles = [r for r in user.roles if r.name != "@everyone"]
        if roles:
            _roles = [
                roles[0].name,
            ] + [f"{r.name:>{len(r.name)+17}}" for r in roles[1:]]
        else:
            _roles = ["None"]

        seen = str(len(set([member.guild.name for member in self.bot.get_all_members() if member.id == user.id])))

        data = "**User**```ini\n"
        data += "[Name]:          {}\n".format(cf.escape(str(user)))
        data += "[ID]:            {}\n".format(user.id)
        data += "[Status]:        {}\n".format(user.status)
        data += "[Servers]:       {} shared\n".format(seen)
        if actplay := discord.utils.get(user.activities, type=discord.ActivityType.playing):
            data += "[Playing]:       {}\n".format(cf.escape(str(actplay.name)))
        if actlisten := discord.utils.get(user.activities, type=discord.ActivityType.listening):
            if isinstance(actlisten, discord.Spotify):
                _form = "{} - {}".format(actlisten.artist, actlisten.title)
            else:
                _form = actlisten.name
            data += "[Listening]:     {}\n".format(cf.escape(_form))
        if actwatch := discord.utils.get(user.activities, type=discord.ActivityType.watching):
            data += "[Watching]:      {}\n".format(cf.escape(str(actwatch.name)))
        if actstream := discord.utils.get(user.activities, type=discord.ActivityType.streaming):
            data += "[Streaming]: [{}]({})\n".format(cf.escape(str(actstream.name)), cf.escape(actstream.url))
        if actcustom := discord.utils.get(user.activities, type=discord.ActivityType.custom):
            if actcustom.name is not None:
                data += "[Custom status]: {}\n".format(cf.escape(str(actcustom.name)))
        data += "[Created]:       {}\n".format(self._dynamic_time(user.created_at))
        if caller != "invoke":
            data += "[Joined]:        {}\n".format(self._dynamic_time(user.joined_at))
            data += "[Roles]:         {}\n".format("\n".join(_roles))
            if len(_roles) > 1:
                data += "\n"
            data += "[In Voice]:      {}\n".format(user.voice.channel if user.voice else None)
            data += "[AFK]:           {}\n".format(user.voice.afk if user.voice else False)
            data += "\n[Avatar URL]:\n{}\n".format(user.avatar_url if user.avatar_url else 'None')
        data += "```"
        await waiting.edit(content=data)

    @commands.command(name='checkid', aliases=['id'])
    @commands.guild_only()
    async def utils_checkid(self, ctx, check_id: int):
        """Resolve any ID to a Guild, Channel, Member, Role or Emoji"""
        await ctx.trigger_typing()

        it_is = False
        roles = [g.roles for g in self.bot.guilds]
        look_at = (
            self.bot.guilds + self.bot.emojis
            + list(itertools.chain.from_iterable(roles))
            + [m for m in self.bot.get_all_members()]
            + [c for c in self.bot.get_all_channels()]
        )

        if ctx.guild.id == check_id:
            it_is = ctx.guild
        elif ctx.channel.id == check_id:
            it_is = ctx.channel
        elif ctx.author.id == check_id:
            it_is = ctx.author

        if not it_is:
            it_is = discord.utils.get(look_at, id=check_id)

        if isinstance(it_is, discord.Guild):
            await ctx.invoke(self.guildinfo, it_is)
        elif isinstance(it_is, discord.abc.GuildChannel):
            await ctx.invoke(self.channelinfo, it_is)
        elif isinstance(it_is, (discord.User, discord.Member)):
            await ctx.invoke(self.userinfo, it_is)
        elif isinstance(it_is, discord.Role):
            await ctx.invoke(self.roleinfo, it_is)
        elif isinstance(it_is, discord.Emoji):
            await ctx.invoke(self.emojiinfo, it_is)
        else:
            await ctx.send(f'Nothing found for ID: `{check_id}`')

    @classmethod
    def _dynamic_time(cls, time):
        try:
            date_join = datetime.datetime.strptime(str(time), "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            time = f"{str(time)}.0"
            date_join = datetime.datetime.strptime(str(time), "%Y-%m-%d %H:%M:%S.%f")
        date_now = datetime.datetime.now(datetime.timezone.utc)
        date_now = date_now.replace(tzinfo=None)
        since_join = date_now - date_join

        mins, secs = divmod(int(since_join.total_seconds()), 60)
        hrs, mins = divmod(mins, 60)
        days, hrs = divmod(hrs, 24)
        mths, wks, days = cls._count_months(days)
        yrs, mths = divmod(mths, 12)

        m = f"{yrs}y {mths}mth {wks}w {days}d {hrs}h {mins}m {secs}s"
        m2 = [x for x in m.split() if x[0] != "0"]
        s = " ".join(m2[:2])
        if s:
            return f"{s} ago"
        else:
            return ""

    @staticmethod
    def _count_months(days):
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
    def _role_from_string(guild, rolename, roles=None):
        if roles is None:
            roles = guild.roles
        role = discord.utils.find(lambda r: r.name.lower() == str(rolename).lower(), roles)
        return role

    @staticmethod
    def sort_channels(channels):
        temp = dict()

        channels = sorted(channels, key=lambda c: c.position)

        for c in channels[:]:
            if isinstance(c, discord.CategoryChannel):
                channels.pop(channels.index(c))
                temp[c] = list()

        for c in channels[:]:
            if c.category:
                channels.pop(channels.index(c))
                temp[c.category].append(c)

        category_channels = sorted(
            [(cat, sorted(chans, key=lambda c: c.position)) for cat, chans in temp.items()],
            key=lambda t: t[0].position,
        )
        return channels, category_channels

    @staticmethod
    def channels_format(channels: list):
        if not channels:
            return []

        def type_name(channel):
            return channel.__class__.__name__[:-7]

        name_justify = max([len(c.name[:24]) for c in channels])
        type_justify = max([len(type_name(c)) for c in channels])
        channel_form = "{name} :: {ctype} :: {cid}"
        return [
            channel_form.format(
                name=c.name[:24].ljust(name_justify),
                ctype=type_name(c).ljust(type_justify),
                cid=c.id,
            )
            for c in channels
        ]

    def category_format(self, cat_chan_tuple: tuple):
        cat = cat_chan_tuple[0]
        chs = cat_chan_tuple[1]
        chfs = self.channels_format(chs)
        if chfs:
            ch_forms = ["\t" + f for f in chfs]
            return "\n".join([f"{cat.name} :: {cat.id}"] + ch_forms)
        else:
            return "\n".join([f"{cat.name} :: {cat.id}"] + ["\tNo Channels"])

    def calculate_diff(self, date1, date2):
        date1str, date2str = self._dynamic_time(date1), self._dynamic_time(date2)
        date1sta, date2sta = date1str.split(" ")[0], date2str.split(" ")[0]

        if len(date1sta) == len(date2sta):
            return (0, 0)
        else:
            ret = len(date2sta) - len(date1sta)
            return (abs(ret), 0 if ret > 0 else 1)
