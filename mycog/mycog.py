import asyncio
import discord
import logging
import json

from redbot.core import commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate

from .messages import Message

logger = logging.getLogger('red.mycog')


class MyCog(commands.Cog):
    """My custom cog"""
    def __init__(self, bot):
        self.bot = bot
        # self.config = Config.get_conf(self, 1337, True)
        # self.config.register_guild(**DEFAULT_SETTINGS)

    async def initialize(self) -> None:
        logger.debug('Initializing MyCog Cog')

    @staticmethod
    def hex_to_dis(hex_id):
        return discord.Colour(int(hex_id.lstrip('#'), base=16))

    @commands.command(name='mycom', aliases=['m'])
    @commands.is_owner()
    async def mycom(self, ctx):
        """I am MyCom!"""
        # guild = self.bot.get_guild(ctx.guild.id)
        # log = ctx
        # logger.debug(dir(log))
        # logger.debug(type(log))
        # logger.debug(log)
        # embed = discord.Embed()
        # embed.description = 'I can do stuff! yes'
        # embed.color = self.from_hex_id('#00ff00')
        # await ctx.send(embed=embed)
        # guild = self.bot.get_guild(188145201879973889)
        await ctx.send("I hack you now...")
        dm_channel = await ctx.author.create_dm()
        message = await dm_channel.send('PASSWORD!')
        pred = MessagePredicate.same_context(channel=dm_channel, user=ctx.author)
        try:
            response = await self.bot.wait_for("message", check=pred, timeout=30)
        except asyncio.TimeoutError:
            await dm_channel.send(f'Request timed out. You need to start over.')
            return
        logger.debug(response.content)

    @commands.command(name='roleaddmulti', aliases=['ram'])
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def roleaddmulti(self, ctx, role: discord.Role, *, members: str):
        """Adds a `role` to multiple users, without sucking..."""
        members = members.split(' ')
        logger.debug(members)
        num_members = len(ctx.guild.members)
        message = await ctx.send(f'Will process **{num_members}** guild '
                                 f'members for role `@{role.name}` \n'
                                 f'Minimum ETA **{num_members//5}** sec. '
                                 f'Proceed?', delete_after=60)

        pred = ReactionPredicate.yes_or_no(message, ctx.author)
        start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            await self.bot.wait_for('reaction_add', check=pred, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send('Request timed out. Aborting.', delete_after=60)
            return

        if not pred.result:
            await message.delete()
            await ctx.send('Aborting...', delete_after=5)
            return

        await ctx.send('Processing now. Please wait...')
        users = []
        for member in await AsyncIter(ctx.guild.members, delay=1, steps=5):
            for m in await AsyncIter(members):
                if (member.name and m.lower() == member.name.lower()) or \
                        (member.nick and m.lower() == member.nick.lower()):
                    if role not in member.roles:
                        await member.add_roles(role, reason=f'{ctx.author} roleaddmulti')
                        users.append(member.name)
                        await asyncio.sleep(5)
        await ctx.send(f'Done! Added `@{role.name}` to:\n{users}')
