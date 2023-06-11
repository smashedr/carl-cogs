import asyncio
import discord
import httpx
import logging
import plotly.express as px
import plotly.io as pio
from io import BytesIO
from typing import Optional, Tuple, Union, Dict, List, Any

from redbot.core import commands, Config

log = logging.getLogger('red.openai')


class ChatGraph(commands.Cog):
    """Custom ChatGraph Cog."""

    guild_default = {
        'blacklist': [],
        'whitelist': [],
    }
    http_options = {
        'follow_redirects': True,
        'timeout': 6,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        self.url: Optional[str] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data = await self.bot.get_shared_api_tokens('api')
        if data and 'url' in data:
            self.url = data['url'].rstrip('/') + '/plotly/'
        log.info('%s: URL: %s', self.__cog_name__, self.url)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @staticmethod
    def calculate_data(history: List[discord.Message]) -> dict:
        """Calculate the member count from the message history"""
        data = {'messages': 0, 'users': 0, 'data': {}}
        for message in history:
            user: discord.User = message.author
            if user.bot:
                continue
            name: str = user.display_name or user.name
            data['messages'] += 1
            if name not in data['data']:
                data['data'][name] = 1
            data['data'][name] += 1
        data['users'] = len(data['data'])
        return data

    async def get_history(self, channel: discord.TextChannel,
                          animation_message: discord.Message,
                          messages: int) -> List[discord.Message]:
        """Get Channel History Interactively"""
        history = []
        counter = 0
        async for msg in channel.history(limit=messages):
            await asyncio.sleep(0.005)
            history.append(msg)
            counter += 1
            if counter % 250 == 0:
                new_embed = discord.Embed(
                    title=f'Fetching messages from #{channel.name}',
                    description=f'This may take a while...\n{counter}/{messages} messages gathered',
                    colour=await self.bot.get_embed_colour(location=channel),
                )
                await animation_message.edit(embed=new_embed)
                await channel.typing()
        return history

    @commands.guild_only()
    @commands.command(name='chatgraph', aliases=['chatchart', 'chatstats'])
    @commands.cooldown(1, 15, commands.BucketType.guild)
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.bot_has_permissions(attach_files=True)
    async def chatgraph(self, ctx: commands.Context,
                        channel: Optional[discord.TextChannel] = None,
                        messages: int = 5000):
        """Generates a pie chart, representing the last 5000 messages in the specified channel."""
        channel = channel or ctx.channel

        # Run Checks
        if 100 > messages > 50000:
            return await ctx.send('100 > messages > 10000')
        if channel.permissions_for(ctx.message.author).read_messages is False:
            return await ctx.send("You're not allowed to access that channel.")
        if channel.permissions_for(ctx.guild.me).read_messages is False:
            return await ctx.send('I cannot read the history of that channel.')
        # blacklisted_channels = await self.config.guild(ctx.guild).channel_deny()
        # if channel.id in blacklisted_channels:
        #     return await ctx.send(f'I am not allowed to create a chatchart of {channel.mention}.')
        # message_limit = await self.config.limit()
        # if (message_limit != 0) and (messages > message_limit):
        #     messages = message_limit

        # Gen Embed and Get History
        embed = discord.Embed(
            title=f'Fetching messages from #{channel.name}',
            description='This might take a while...',
            colour=await self.bot.get_embed_colour(location=channel)
        )
        animation_message: discord.Message = await ctx.send(embed=embed)
        history = await self.get_history(channel, animation_message, messages)
        data: Dict[str, Any] = self.calculate_data(history)

        # No Members Found
        if not data['users']:
            await animation_message.delete()
            return await ctx.send(f'No user history found in channel {channel.mention}')

        # Gen Plotly Data
        users, totals = [], []
        for user, total in data['data'].items():
            users.append(user)
            totals.append(total)
        pio.templates.default = 'plotly_dark'
        df = {'messages': totals, 'users': users}
        title = f'{ctx.guild.name} #{channel.name} last {data["messages"]} Messages'
        msg = f'**{ctx.guild.name}** {channel.mention} last **{data["messages"]}** Messages:'
        fig = px.pie(df, values='messages', names='users', title=title)

        # Create file object
        file = BytesIO()
        file.write(fig.to_image())
        file.seek(0)
        file = discord.File(file, f'{channel.name}-{messages}.png')

        # Set msg, check url, post data, update msg, and send
        if self.url:
            html = fig.to_html(include_plotlyjs='cdn', config={'displaylogo': False})
            log.debug('html:type: %s', type(html))
            href = await self.post_data(html)
            log.debug('href: %s', href)
            if href:
                msg = f'{msg}\n<{self.url}{href}>'
        await animation_message.delete()
        await ctx.send(msg, file=file)

    async def post_data(self, html: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.post(url=self.url, content=html)
                log.debug('r.status_code: %s', r.status_code)
                r.raise_for_status()
                return r.text
        except Exception as error:
            log.debug(error)
            return None

    # @checks.mod_or_permissions(manage_guild=True)
    # @commands.guild_only()
    # @commands.command(aliases=['guildchart'])
    # @commands.cooldown(1, 30, commands.BucketType.guild)
    # @commands.max_concurrency(1, commands.BucketType.guild)
    # @commands.bot_has_permissions(attach_files=True)
    # async def serverchart(self, ctx: commands.Context, messages: int = 1000):
    #     """
    #     Generates a pie chart, representing the last 1000 messages from every allowed channel in the server.
    #
    #     As example:
    #     For each channel that the bot is allowed to scan. It will take the last 1000 messages from each channel.
    #     And proceed to build a chart out of that.
    #     """
    #     if messages < 5:
    #         return await ctx.send("Don't be silly.")
    #     channel_list = []
    #     blacklisted_channels = await self.config.guild(ctx.guild).channel_deny()
    #     for channel in ctx.guild.text_channels:
    #         channel: discord.TextChannel
    #         if channel.id in blacklisted_channels:
    #             continue
    #         if channel.permissions_for(ctx.message.author).read_messages is False:
    #             continue
    #         if channel.permissions_for(ctx.guild.me).read_messages is False:
    #             continue
    #         channel_list.append(channel)
    #
    #     if len(channel_list) == 0:
    #         return await ctx.send('There are no channels to read... This should theoretically never happen.')
    #
    #     embed = discord.Embed(
    #         description='Fetching messages from the entire server this **will** take a while.',
    #         colour=await self.bot.get_embed_colour(location=ctx.channel),
    #     )
    #     global_fetch_message = await ctx.send(embed=embed)
    #     global_history = []
    #
    #     for channel in channel_list:
    #         embed = discord.Embed(
    #             title=f'Fetching messages from #{channel.name}',
    #             description='This might take a while...',
    #             colour=await self.bot.get_embed_colour(location=channel)
    #         )
    #         loading_message = await ctx.send(embed=embed)
    #         try:
    #             history = await self.fetch_channel_history(channel, loading_message, messages)
    #             global_history += history
    #             await loading_message.delete()
    #         except discord.errors.Forbidden:
    #             try:
    #                 await loading_message.delete()
    #             except discord.NotFound:
    #                 continue
    #         except discord.NotFound:
    #             try:
    #                 await loading_message.delete()
    #             except discord.NotFound:
    #                 continue
    #
    #     msg_data = self.calculate_member_perc(global_history)
    #     # If no members are found.
    #     if len(msg_data['users']) == 0:
    #         try:
    #             await global_fetch_message.delete()
    #         except discord.NotFound:
    #             pass
    #         return await ctx.send(f'Only bots have sent messages in this server... Wauw...')
    #
    #     top_twenty, others = self.calculate_top(msg_data)
    #     chart = await self.create_chart(top_twenty, others, ctx.guild)
    #
    #     try:
    #         await global_fetch_message.delete()
    #     except discord.NotFound:
    #         pass
    #     await ctx.send(file=discord.File(chart, 'chart.png'))
    #
    # @checks.mod_or_permissions(manage_channels=True)
    # @commands.guild_only()
    # @commands.command()
    # async def ccdeny(self, ctx, channel: discord.TextChannel):
    #     """Add a channel to deny chatchart use."""
    #     channel_list = await self.config.guild(ctx.guild).channel_deny()
    #     if channel.id not in channel_list:
    #         channel_list.append(channel.id)
    #     await self.config.guild(ctx.guild).channel_deny.set(channel_list)
    #     await ctx.send(f"{channel.mention} was added to the deny list for chatchart.")
    #
    # @checks.mod_or_permissions(manage_channels=True)
    # @commands.guild_only()
    # @commands.command()
    # async def ccdenylist(self, ctx):
    #     """List the channels that are denied."""
    #     no_channels_msg = "Chatchart is currently allowed everywhere in this server."
    #     channel_list = await self.config.guild(ctx.guild).channel_deny()
    #     if not channel_list:
    #         msg = no_channels_msg
    #     else:
    #         msg = "Chatchart is not allowed in:\n"
    #         remove_list = []
    #         for channel in channel_list:
    #             channel_obj = self.bot.get_channel(channel)
    #             if not channel_obj:
    #                 remove_list.append(channel)
    #             else:
    #                 msg += f"{channel_obj.mention}\n"
    #         if remove_list:
    #             new_list = [x for x in channel_list if x not in remove_list]
    #             await self.config.guild(ctx.guild).channel_deny.set(new_list)
    #             if len(remove_list) == len(channel_list):
    #                 msg = no_channels_msg
    #     await ctx.send(msg)
    #
    # @checks.mod_or_permissions(manage_channels=True)
    # @commands.guild_only()
    # @commands.command()
    # async def ccallow(self, ctx, channel: discord.TextChannel):
    #     """Remove a channel from the deny list to allow chatchart use."""
    #     channel_list = await self.config.guild(ctx.guild).channel_deny()
    #     if channel.id in channel_list:
    #         channel_list.remove(channel.id)
    #     else:
    #         return await ctx.send("Channel is not on the deny list.")
    #     await self.config.guild(ctx.guild).channel_deny.set(channel_list)
    #     await ctx.send(f"{channel.mention} will be allowed for chatchart use.")
    #
    # @checks.is_owner()
    # @commands.command()
    # async def cclimit(self, ctx, limit_amount: int = None):
    #     """
    #     Limit the amount of messages someone can request.
    #
    #     Use `0` for no limit.
    #     """
    #     if limit_amount is None:
    #         return await ctx.send_help()
    #     if limit_amount < 0:
    #         return await ctx.send("You need to use a number larger than 0.")
    #     await self.config.limit.set(limit_amount)
    #     await ctx.send(f"Chatchart is now limited to {limit_amount} messages.")
