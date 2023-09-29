import discord
import logging
from typing import List, Optional, Union

from redbot.core import app_commands, commands, Config
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.reactvote')


class ReactVote(commands.Cog):
    """Carl's ReactVote Cog"""

    guild_default = {
        'enabled': True,
        'downvote': 0,
        'upvote': 0,
        'channels': [],
        'icons': ['👍', '👎'],
        'votes': 3,
    }

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Watch for reactions added to a message in an enabled channel"""
        if not payload.member or payload.member.bot:
            return log.debug('no member or member is bot')
        if not payload.guild_id or not payload.channel_id or not payload.message_id:
            return log.debug('no guild_id or channel_id or message_id')
        log.debug('payload.guild_id: %s', payload.guild_id)
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        log.debug('guild: %s', guild)
        if not guild:
            return log.debug('no guild')
        config: dict = await self.config.guild(guild).all()
        log.debug('config: %s', config)
        if not config['enabled']:
            return log.debug('config.enabled: %s', config['enabled'])
        log.debug('config.channels: %s', config['channels'])
        if payload.channel_id not in config['channels']:
            return log.debug('channel not enabled')
        if str(payload.emoji) not in config['icons']:
            return log.debug('emoji not in list')
        log.debug('payload.channel_id: %s', payload.channel_id)
        channel: discord.TextChannel = guild.get_channel(payload.channel_id)
        log.debug('channel: %s', channel)
        if not channel:
            return log.debug('no channel')
        log.debug('payload.message_id: %s', payload.message_id)
        message: discord.Message = await channel.fetch_message(payload.message_id)
        log.debug('message: %s', message)
        if not message:
            return log.debug('no message')
        await self.process_message(message, config)

    async def process_message(self, message: discord.Message, config: dict):
        upvotes = await self.count_reactions(message, config['icons'][0])
        log.debug(f'upvotes: {upvotes}')
        downvotes = await self.count_reactions(message, config['icons'][1])
        log.debug(f'downvotes: {downvotes}')
        log.debug(f'Total DOWN: {downvotes-upvotes}')
        log.debug(f'Total UP: {upvotes-downvotes}')
        log.debug(f"config.votes: {config['votes']}")
        if downvotes-upvotes >= config['votes']:
            await self.process_downvote(message, config)
        if upvotes-downvotes >= config['votes']:
            await self.process_upvote(message, config)

    async def process_downvote(self, message: discord.Message, config):
        channel: discord.TextChannel = message.guild.get_channel(config['downvote'])
        log.debug(f'channel: {channel}')
        if not channel:
            return log.warning('404: Down Vote Channel NOT FOUND!')
        repost: discord.Message = await self.repost_message(message, channel)
        await message.channel.send(f"Message {repost.jump_url} deleted by **{config['votes']}** down votes.",
                                   delete_after=300)

    async def process_upvote(self, message: discord.Message, config):
        channel: discord.TextChannel = message.guild.get_channel(config['upvote'])
        log.debug(f'channel: {channel}')
        if not channel:
            await message.channel.send(f"Message {message.jump_url} pinned by **{config['votes']}** up votes.",
                                       delete_after=120)
            return await message.pin()

        repost: discord.Message = await self.repost_message(message, channel)
        await message.channel.send(f"Message {repost.jump_url} reposted by **{config['votes']}** up votes.",
                                   delete_after=300)

    @staticmethod
    async def count_reactions(message: discord.Message, icon: str, exclude_bots=True):
        count = 0
        for react in message.reactions:
            if str(react.emoji) == icon:
                count = react.count
                if exclude_bots:
                    async for user in react.users():
                        if user.bot:
                            count -= 1
        return count

    @staticmethod
    async def repost_message(message: discord.Message, destination: discord.TextChannel,
                             silent=True, delete=True) -> discord.Message:
        files = []
        for attachment in message.attachments:
            files.append(await attachment.to_file())
        embeds: List[discord.Embed] = [e for e in message.embeds if e.type == 'rich']
        content = (f'**ReactVote** DownVote from {message.channel.mention} '
                   f'on <t:{int(message.created_at.timestamp())}:D> '
                   f'by {message.author.mention}\n{message.content}')
        repost = await destination.send(content, embeds=embeds, files=files, silent=silent,
                                        allowed_mentions=discord.AllowedMentions.none())
        if delete:
            await message.delete()
        return repost

    @commands.group(name='reactvote', aliases=['rv'])
    @commands.guild_only()
    @commands.admin()
    async def _reactvote(self, ctx: commands.Context):
        """Options for managing ReactVote."""

    @_reactvote.command(name='toggle', aliases=['enable', 'disable', 'on', 'off'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _reactvote_toggle(self, ctx: commands.Context):
        """Enable/Disable ReactVote"""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await self.config.guild(ctx.guild).enabled.set(False)
            return await ctx.send(f'\U0001F6D1 {self.__cog_name__} Disabled.')
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(f'\U00002705 {self.__cog_name__} Enabled.')

    @_reactvote.command(name='channels')
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _reactvote_channels(self, ctx: commands.Context):
        """Set Channels for ReactVote"""
        view = ChannelView(self, ctx.author)
        msg = 'Select channels for **ReactVote**:'
        await view.send_initial_message(ctx, msg, True)

    @_reactvote.command(name='votes', aliases=['vote'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _reactvote_votes(self, ctx: commands.Context, votes: int):
        """Set Up and Down Vote Emoji for ReactVote"""
        log.debug(f'votes: {votes}')
        if votes < 1:
            return await ctx.send(f"Votes must be a positive integer. Not: `{votes}`")
        config: dict = await self.config.guild(ctx.guild).votes.set(votes)
        log.debug(f'config: {config}')
        await ctx.send(f"\U00002705 Total Votes Required: `{votes}`")
        await self.sync_settings(ctx.guild)

    @_reactvote.command(name='emoji', aliases=['emojis', 'icons'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _reactvote_emoji(self, ctx: commands.Context):
        """Set Up and Down Vote Emoji for ReactVote"""
        # TODO: Finish This
        # config: dict = await self.config.guild(ctx.guild).all()
        # await ctx.send(f"React to this message with new Up/Down Vote Emoji.\n"
        #                f"{config['icons'][0]} {config['icons'][1]}")
        await ctx.send('\U000026A0\U0000FE0F INOP: This has not been implemented.')
        # await self.sync_settings(ctx.guild)

    @_reactvote.command(name='downvote', aliases=['downvoted', 'delete'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _reactvote_downvote(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set ReactVote Delete Channel"""
        log.debug('channel: %s', channel)
        log.debug('channel.id: %s', channel.id)
        await self.config.guild(ctx.guild).downvote.set(channel.id)
        await ctx.send(f'\U00002705 ReactVote Down Voted Messages Channel: {channel.mention}', silent=True)
        await self.sync_settings(ctx.guild)

    @_reactvote.command(name='upvoted', aliases=['upvote', 'starboard'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _reactvote_upvoted(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set ReactVote Upvote Channel"""
        log.debug('channel: %s', channel)
        log.debug('channel.id: %s', channel.id)
        await self.config.guild(ctx.guild).upvote.set(channel.id)
        await ctx.send(f'\U00002705 ReactVote Up Voted Messages Channel: {channel.mention}', silent=True)
        await self.sync_settings(ctx.guild)

    @_reactvote.command(name='status', aliases=['settings', 'config'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _reactvote_status(self, ctx: commands.Context):
        """Show ReactVote Settings"""
        config = await self.config.guild(ctx.guild).all()
        log.debug(config)
        status = '✅ **Enabled**' if config['enabled'] else '🛑 **NOT ENABLED**'
        channels = [ctx.guild.get_channel(x) for x in config['channels']]
        mentions = cf.humanize_list([x.mention for x in channels]) if channels else '**NO Channels**'
        log.debug('mentions: %s', mentions)
        downvote = ctx.guild.get_channel(config['downvote'])
        downvote = downvote.mention if downvote else 'Not Set'
        log.debug('downvote: %s', downvote)
        upvote = ctx.guild.get_channel(config['upvote'])
        upvote = upvote.mention if upvote else 'Not Set'
        log.debug('upvote: %s', upvote)
        out = (f"ReactVote {status}\nChannels: {mentions}\n"
               f"Downvote Channel: {downvote}\n"
               f"Upvote Channel: {upvote}\n"
               f"Total Votes Required: `{config['votes']}`\n"
               f"Up: {config['icons'][0]} Down: {config['icons'][1]}")
        await ctx.send(out)

    async def sync_settings(self, guild: discord.Guild):
        config = await self.config.guild(guild).all()
        if config['upvote']:
            channel: discord.TextChannel = guild.get_channel(config['upvote'])
            topic = f"Messages w/ +{config['votes']} {config['icons'][0]} will be reposted here."
            if channel.topic != topic:
                await channel.edit(topic=topic)
        if config['downvote']:
            channel: discord.TextChannel = guild.get_channel(config['downvote'])
            topic = f"Messages w/ +{config['votes']} {config['icons'][1]} will be archived here."
            if channel.topic != topic:
                await channel.edit(topic=topic)


class ChannelView(discord.ui.View):
    def __init__(self, cog, author: Union[discord.Member, discord.User, int],
                 timeout: int = 60 * 3, delete_after: int = 60):
        self.cog = cog
        self.user_id: int = author.id if hasattr(author, 'id') else int(author)
        self.delete_after: int = delete_after
        self.ephemeral: bool = False
        self.message: Optional[discord.Message] = None
        super().__init__(timeout=timeout)

    async def on_timeout(self):
        await self.message.delete()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.user_id:
            return True
        msg = '\U0001F534 Looks like you did not create this response.'
        await interaction.response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
        return False

    async def send_initial_message(self, ctx, message: Optional[str] = None,
                                   ephemeral: bool = False, **kwargs) -> discord.Message:
        self.ephemeral = ephemeral
        self.message = await ctx.send(content=message, view=self, ephemeral=self.ephemeral, **kwargs)
        return self.message

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text],
                       min_values=0, max_values=25)
    async def select_channels(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        response = interaction.response
        channels: List[app_commands.AppCommandChannel] = []
        for value in select.values:
            channels.append(value)
        if not channels:
            await self.cog.config.guild(interaction.guild).channels.set([])
            msg = '\U00002705 ReactVote Channels Cleared.'
            return await response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
        ids = [x.id for x in channels]
        await self.cog.config.guild(interaction.guild).channels.set(ids)
        names = [x.name for x in channels]
        msg = f'\U00002705 ReactVote Channels Set to: {cf.humanize_list(names)}'
        return await response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
