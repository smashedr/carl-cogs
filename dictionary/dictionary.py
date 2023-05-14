import datetime
import discord
import httpx
import logging
import urllib.parse

from redbot.core import commands

log = logging.getLogger('red.dictionary')


class Dictionary(commands.Cog):
    """Carl's Dictionary Cog"""

    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }

    def __init__(self, bot):
        self.bot = bot
        self.loop = None

    async def cog_load(self):
        log.info(f'{self.__cog_name__}: Cog Load')

    async def cog_unload(self):
        log.info(f'{self.__cog_name__}: Cog Unload')

    @commands.command(name='dictionary', aliases=['lookup', 'definition'])
    async def dictionary(self, ctx, *, word):
        """Get the Dictionary definition for provided <word>."""
        safe_word = urllib.parse.quote_plus(word)
        url = f'https://api.dictionaryapi.dev/api/v2/entries/en/{safe_word}'
        try:
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url)
            if not r.is_success:
                r.raise_for_status()
        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error performing lookup: `{error}`')
            return

        result = r.json()

        if len(result) < 1:
            await ctx.send(f'No results for: `{word}`')
            return

        data = result[0]
        em = discord.Embed()
        em.colour = discord.Colour.blue()
        if data['phonetics']:
            url = 'https:{}'.format(data['phonetics'][0]['audio'])
            em.set_author(name=data['phonetics'][0]['text'], url=url)
        em.title = data['word']
        # if 'origin' in data:
        #     em.description = data['origin']
        for d in data['meanings']:
            value = ''
            if 'definition' in d['definitions'][0]:
                value = f"**Definition:** {d['definitions'][0]['definition']}"
            if 'example' in d['definitions'][0]:
                value += f"\n**Example:** {d['definitions'][0]['example']}"
            em.add_field(name=d['partOfSpeech'].title(), value=value, inline=False)

        # em.set_thumbnail(url=self.bot.user.avatar_url)
        # em.set_footer(text=f'ID: {ctx.author.id}', icon_url=ctx.author.avatar_url)

        em.timestamp = datetime.datetime.utcnow()
        await ctx.send(embed=em)

    @commands.command(name='urban', aliases=['urbandict', 'urbandictionary'])
    async def urban(self, ctx, *, word):
        """Get the Urban Dictionary definition for provided <word>."""
        safe_word = urllib.parse.quote_plus(word)
        url = f'https://api.urbandictionary.com/v0/define?term={safe_word}'
        try:
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url)
            if not r.is_success:
                r.raise_for_status()
        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error performing lookup: `{error}`')
            return

        result = r.json()

        data = result['list']
        if len(data) < 1:
            await ctx.send(f'No results for: `{word}`')
            return

        em = discord.Embed()
        em.colour = discord.Colour.blue()
        em.title = word
        em.description = f"https://www.urbandictionary.com/define.php?term={safe_word}"

        # for d in data['meanings']:
        #     value = ''
        #     if 'definition' in d['definitions'][0]:
        #         value = f"**Definition:** {d['definitions'][0]['definition']}"
        #     if 'example' in d['definitions'][0]:
        #         value += f"\n**Example:** {d['definitions'][0]['example']}"

        d = data[0]
        thumbs = d['thumbs_up'] - d['thumbs_down']
        title = f"{d['word']} - {thumbs} ({d['thumbs_up']}/{d['thumbs_down']})"
        value = d['definition'][:600]
        if len(d['definition']) > 600:
            value += '...'
        em.add_field(name=title, value=value, inline=False)

        # em.set_thumbnail(url=self.bot.user.avatar_url)
        # em.set_footer(text=f'ID: {ctx.author.id}', icon_url=ctx.author.avatar_url)

        em.timestamp = datetime.datetime.utcnow()
        await ctx.send(embed=em)

    # async def perform_lookup(self, ctx, url) -> dict:
    #     try:
    #         async with httpx.AsyncClient(**self.http_options) as client:
    #             r = await client.get(url)
    #             result = r.json()
    #             log.debug(result)
    #         if not r.is_success:
    #             r.raise_for_status()
    #     except Exception as error:
    #         log.exception(error)
    #         await ctx.send(f'Error performing lookup: `{error}`')
    #         return {}
    #
    #     return result
