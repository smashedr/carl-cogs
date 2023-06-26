import datetime
import discord
import httpx
import logging
import urllib.parse
from typing import Union

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

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.content:
            return
        split = message.content.split()
        if len(split) < 2:
            return
        trigger = split[0].lower()
        query = ' '.join(split[1:])
        if not trigger or not query:
            return

        if trigger in ['define', 'lookup', 'dictionary']:
            log.debug('trigger: %s', trigger)
            log.debug('query: %s', query)
            await self.dictionary(message.channel, term=query)
        if trigger in ['urban']:
            log.debug('trigger: %s', trigger)
            log.debug('query: %s', query)
            await self.urban(message.channel, term=query)

    @commands.command(name='dictionary', aliases=['lookup', 'definition', 'define'])
    async def dictionary(self, ctx: Union[commands.Context, discord.TextChannel],
                         *, term: str):
        """Get the Dictionary definition for provided <word>."""
        await ctx.typing()
        safe_term = urllib.parse.quote_plus(term)
        log.debug(safe_term)
        url = f'https://api.dictionaryapi.dev/api/v2/entries/en/{safe_term}'
        log.debug(url)
        try:
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url)
                r.raise_for_status()
        except Exception as error:
            log.exception(error)
            return await ctx.send(f'Error performing lookup: `{error}`')

        result = r.json()
        if len(result) < 1:
            return await ctx.send(f'No results for: `{term}`')

        data = result[0]
        log.debug(data)
        em = discord.Embed()
        em.colour = discord.Colour.blue()
        author = {'name': data['word']}
        if 'phonetics' in data:
            for text in data['phonetics']:
                log.debug(text)
                if 'audio' in text and text['audio']:
                    # em.set_author(name='🔊 ' + text['text'], url=text['audio'])
                    author.update({'url': text['audio']})
                    author['name'] = '🔊 ' + author['name']
                    break
        em.set_author(**author)
        log.debug(2)
        # em.title = data['word']
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
        log.debug(3)
        await ctx.send(embed=em)

    @commands.command(name='urban', aliases=['urbandict', 'urbandictionary'])
    async def urban(self, ctx: Union[commands.Context, discord.TextChannel],
                    *, term: str):
        """Get the Urban Dictionary definition for provided <word>."""
        safe_word = urllib.parse.quote_plus(term)
        url = f'https://api.urbandictionary.com/v0/define?term={safe_word}'
        await ctx.typing()
        try:
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url)
                r.raise_for_status()
        except Exception as error:
            log.exception(error)
            return await ctx.send(f'Error performing lookup: `{error}`')

        result = r.json()
        data = result['list']
        if len(data) < 1:
            return await ctx.send(f'No results for: `{term}`')

        em = discord.Embed()
        em.colour = discord.Colour.blue()
        em.title = term
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
