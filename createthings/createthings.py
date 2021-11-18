import logging
import requests

from redbot.core import commands
from redbot.core.utils import AsyncIter

logger = logging.getLogger('red.createroles')

ROLE_WOW_CLASSES = {
    'Druid': '16743434',
    'Hunter': '11195250',
    'Mage': '4179947',
    'Paladin': '16026810',
    'Priest': '16777215',
    'Rogue': '16774248',
    'Shaman': '28893',
    'Warlock': '8882414',
    'Warrior': '13015917',
}

EMOJI_WOW_CLASSES = {
    'wowdruid': 'https://i.imgur.com/RLmjz9a.png',
    'wowhunter': 'https://i.imgur.com/ggJAPTr.png',
    'wowmage': 'https://i.imgur.com/vC1DkZL.png',
    'wowpaladin': 'https://i.imgur.com/F9IPIiH.png',
    'wowpriest': 'https://i.imgur.com/VesSiYs.png',
    'wowrogue': 'https://i.imgur.com/XyfURXG.png',
    'wowshaman': 'https://i.imgur.com/7TvpORt.png',
    'wowwarlock': 'https://i.imgur.com/VXS6vGT.png',
    'wowwarrior': 'https://i.imgur.com/AuOdNiI.png',
}

ROLE_SETS = {
    'wowclasses': ROLE_WOW_CLASSES,
}

EMOJI_SETS = {
    'wowclasses': EMOJI_WOW_CLASSES,
}


class Createthings(commands.Cog):
    """Carl's Createthings Cog"""
    def __init__(self, bot):
        self.bot = bot

    async def initialize(self) -> None:
        logger.debug('Initializing Createthings Cog')

    @staticmethod
    async def create_role_set(ctx, role_set):
        results = []
        async for name, color in AsyncIter(role_set.items()):
            logger.debug(f'{name} - {color}')
            match = [r async for r in AsyncIter(ctx.guild.roles) if r.name == name]
            if match:
                results.append(f'@{name} - Already Exist ⛔')
                logger.debug('Role %s already exists.', name)
                continue

            logger.debug('Creating Role: %s', name)
            role = await ctx.guild.create_role(
                name=name, color=int(color),
                reason=f'Carl createroles command used by {ctx.author.name}',
            )
            results.append(f'@{role.name} - Created Role ✅')

        return results

    @staticmethod
    async def create_emoji_set(ctx, emoji_set):
        results = []
        async for name, url in AsyncIter(emoji_set.items()):
            logger.debug(f'{name} - {url}')
            match = [e async for e in AsyncIter(ctx.guild.emojis) if e.name == name]
            if match:
                results.append(f'{name}  - Already Exist ⛔')
                logger.debug('Emoji name exists: %s', name)
                continue

            logger.debug('Creating emoji: %s', name)
            emoji = await ctx.guild.create_custom_emoji(
                name=name, image=get_discord_image_data(url),
                reason=f'Carl createemoji command used by {ctx.author.name}',
            )
            results.append(f'{emoji.name} - Creation Success ✅')

        return results

    @commands.group(name='createroles', aliases=['cr'])
    @commands.guild_only()
    @commands.admin()
    async def createroles(self, ctx):
        """Create pre-defined Role sets."""

    @createroles.command(name='list', aliases=["l"])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def createroles_list(self, ctx):
        """List configured role sets that can be created."""
        await ctx.trigger_typing()
        role_sets = list(ROLE_SETS.keys())
        await ctx.send(f'Available role sets:\n{role_sets}')

    @createroles.command(name='create', aliases=["c"])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def createroles_create(self, ctx, *, name: str):
        """Create a Role set with the given name. View sets with `list`."""
        await ctx.trigger_typing()
        name = name.lower()
        logger.debug(name)
        if name not in ROLE_SETS:
            await ctx.send(f'Role set not found: {name}\n'
                           f'Use `{ctx.prefix}createroles list`')
            return

        await ctx.send(f'Creating role set: {name}')
        async with ctx.channel.typing():
            results = await self.create_role_set(ctx, ROLE_SETS[name])
            results = ['```' + '\n'.join(results) + '```']
            out = [f'Role Creation Complete. Results:'] + results
        await ctx.send('\n'.join(out))

    @commands.group(name='createemoji', aliases=['ce'])
    @commands.guild_only()
    @commands.admin()
    async def createemoji(self, ctx):
        """Create pre-defined Emoji sets."""

    @createemoji.command(name='list', aliases=["l"])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def createemoji_list(self, ctx):
        """List configured emoji sets that can be created."""
        await ctx.trigger_typing()
        emoji_sets = list(EMOJI_SETS.keys())
        await ctx.send(f'Available emoji sets:\n{emoji_sets}')

    @createemoji.command(name='create', aliases=["c"])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def createemoji_create(self, ctx, *, name: str):
        """Create an Emoji set with the given name. View sets with `list`."""
        name = name.lower()
        logger.debug(name)
        if name not in EMOJI_SETS:
            await ctx.send(f'Emoji set not found: **{name}**\n'
                           f'Use `{ctx.prefix}createemoji list`')
            return

        emoji = EMOJI_SETS[name]
        slots = ctx.guild.emoji_limit - len(ctx.guild.emojis)
        if slots <= len(emoji):
            await ctx.send(f'You requested to create {len(emoji)} emoji '
                           f'but only have room for {slots}, make room.')
            return

        await ctx.send(f'Creating emoji set: **{name}**')
        async with ctx.channel.typing():
            results = await self.create_emoji_set(ctx, EMOJI_SETS[name])
            results = ['```' + '\n'.join(results) + '```']
            out = [f'Emoji Creation Complete. Results:'] + results
        await ctx.send('\n'.join(out))


def get_discord_image_data(url=None, content=None):
    if not url and content:
        raise ValueError('url or content required')
    if url:
        logger.debug('fetching url: %s', url)
        r = requests.get(url, timeout=10)
        content = r.content
    return content
