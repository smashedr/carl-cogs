import logging
import httpx

from redbot.core import commands
from redbot.core.utils import AsyncIter

log = logging.getLogger('red.createroles')

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

    async def cog_load(self):
        log.info(f'{self.__cog_name__}: Cog Load')

    async def cog_unload(self):
        log.info(f'{self.__cog_name__}: Cog Unload')

    @staticmethod
    async def create_role_set(ctx, role_set):
        results = []
        async for name, color in AsyncIter(role_set.items()):
            log.debug(f'{name} - {color}')
            match = [r async for r in AsyncIter(ctx.guild.roles) if r.name == name]
            if match:
                results.append(f'{match[0].mention} - Already Exist ⛔')
                log.debug('Role %s already exists.', name)
                continue

            log.debug('Creating Role: %s', name)
            role = await ctx.guild.create_role(
                name=name, color=int(color),
                reason=f'Carl createroles command used by {ctx.author.name}',
            )
            results.append(f'{role.mention} - Created Role ✅')

        return results

    @staticmethod
    async def create_emoji_set(ctx, emoji_set):
        results = []
        async for name, url in AsyncIter(emoji_set.items()):
            log.debug(f'{name} - {url}')
            match = [e async for e in AsyncIter(ctx.guild.emojis) if e.name == name]
            if match:
                results.append(f'{match[0]}  - Already Exist ⛔')
                log.debug('Emoji name exists: %s', name)
                continue

            log.debug('Creating emoji: %s', name)
            emoji = await ctx.guild.create_custom_emoji(
                name=name, image=get_discord_image_data(url),
                reason=f'Carl createemoji command used by {ctx.author.name}',
            )
            results.append(f'{emoji} - Creation Success ✅')

        return results

    @commands.group(name='createroles', aliases=['cr'])
    @commands.guild_only()
    @commands.admin()
    async def createroles(self, ctx):
        """Create pre-defined Role sets."""

    @createroles.command(name='list', aliases=["l"])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def createroles_list(self, ctx, name: str = None):
        """List configured role sets that can be created."""
        await ctx.typing()
        if name and name in ROLE_SETS:
            role_sets = list(ROLE_SETS[name].keys())
            await ctx.send(f'Roles in set `{name}`:\n```{role_sets}```')
        else:
            role_sets = list(ROLE_SETS.keys())
            await ctx.send(f'Available role sets:\n```{role_sets}```')

    @createroles.command(name='create', aliases=["c"])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def createroles_create(self, ctx, *, name: str):
        """Create a Role set with the given name. View sets with `list`."""
        await ctx.typing()
        name = name.lower()
        log.debug(name)
        if name not in ROLE_SETS:
            await ctx.send(f'Role set not found: {name}\n'
                           f'Use `{ctx.prefix}createroles list`')
            return

        await ctx.send(f'Creating role set: {name}')
        async with ctx.channel.typing():
            results = await self.create_role_set(ctx, ROLE_SETS[name])
            out = [f'Role Creation Complete. Results:'] + results
        await ctx.send('\n'.join(out))

    @commands.group(name='createemoji', aliases=['ce'])
    @commands.guild_only()
    @commands.admin()
    async def createemoji(self, ctx):
        """Create pre-defined Emoji sets."""

    @createemoji.command(name='list', aliases=["l"])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def createemoji_list(self, ctx, name: str = None):
        """List configured emoji sets that can be created."""
        await ctx.typing()
        if name and name in EMOJI_SETS:
            emoji_sets = list(EMOJI_SETS[name].keys())
            await ctx.send(f'Emoji in set `{name}`:\n```{emoji_sets}```')
        else:
            emoji_sets = list(EMOJI_SETS.keys())
            await ctx.send(f'Available emoji sets:\n```{emoji_sets}```')

    @createemoji.command(name='create', aliases=["c"])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def createemoji_create(self, ctx, *, name: str):
        """Create an Emoji set with the given name. View sets with `list`."""
        name = name.lower()
        log.debug(name)
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
            out = [f'Emoji Creation Complete. Results:'] + results
        await ctx.send('\n'.join(out))


def get_discord_image_data(url=None, content=None):
    if not url and content:
        raise ValueError('url or content required')

    if not url:
        return content

    log.debug('fetching url: %s', url)
    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }
    async with httpx.AsyncClient(**http_options) as client:
        r = await client.get(url)
    if not r.is_success:
        r.raise_for_status()
    return r.content
