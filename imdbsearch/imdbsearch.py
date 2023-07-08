import asyncio
import discord
import logging
from typing import Union
from imdb import Cinemagoer

from redbot.core import app_commands, commands
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.imdbsearch')


class Imdblookup(commands.Cog):
    """Carl's Imdblookup Cog"""

    title_url = 'https://www.imdb.com/title/tt{id}/'

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    # @commands.Cog.listener(name='on_message_without_command')
    # async def on_message_without_command(self, message: discord.Message):
    #     if message.author.bot or not message.content:
    #         return
    #     split = message.content.split()
    #     if len(split) < 2:
    #         return
    #     trigger = split[0].lower()
    #     query = ' '.join(split[1:])
    #     if not trigger or not query:
    #         return

    @commands.hybrid_command(name='imdb', aliases=['imdbsearch'])
    @app_commands.describe(search='IMDB Search String')
    async def _imdb(self, ctx: Union[commands.Context, discord.TextChannel], *, search: str):
        """IMDB <search>"""
        await ctx.typing()
        ia = Cinemagoer()
        results = ia.search_movie(search)
        if not results:
            return await ctx.send(f'No results for: `{search}`')

        msg_list = [f'Results for: **{search}**\n```']
        for i, result in enumerate(results, 1):
            year = f" ({result['year']})" if 'year' in result else ''
            msg_list.append(f"{i}. {result['title']}{year} - {result['kind']}")
            if i == 9:
                break

        msg = '\n'.join(msg_list) + '``` For more details **enter a number** in chat...'
        initial_message = await ctx.send(msg)
        predicate = MessagePredicate.same_context(ctx=ctx)
        try:
            message = await ctx.bot.wait_for("message", check=predicate, timeout=120)
        except asyncio.TimeoutError:
            return
        if not message.content.isdigit():
            return

        await initial_message.delete()
        await ctx.typing()
        result = results[int(message.content) - 1]
        data = ia.get_movie(result.movieID)

        log.debug('-'*40)
        log.debug(data.keys())
        log.debug('-'*40)
        # for k, v in data.items():
        #     log.debug('%s: %s', k, v)
        # log.debug('-'*40)
        # log.debug('localized title: %s', data['localized title'])

        url = self.title_url.format(id=data['imdbID'])
        log.debug('url: %s', url)
        genres = cf.humanize_list(data['genres'])
        log.debug('genres: %s', genres)
        cast_names = []
        for i, cast in enumerate(data['cast'], 1):
            cast_names.append(cast['name'])
            if i == 3:
                break
        cast = cf.humanize_list(cast_names)
        log.debug('cast: %s', cast)

        em = discord.Embed()
        em.colour = discord.Colour(int('0xf5c518', 16))

        if 'cover url' in data:
            log.debug('cover url: %s', data['cover url'])
            em.set_thumbnail(url=data['cover url'])
        elif 'full-size cover url' in data:
            log.debug('full-size cover url: %s', data['full-size cover url'])
            em.set_thumbnail(url=data['full-size cover url'])

        log.debug('kind: %s', data['kind'])
        if data['kind'].lower() == 'tv series':
            log.debug('--- TV SERIES ---')
            data['kind'] = 'TV Series'
            years = data['series years']
            if data['series years'].endswith('-'):
                years = data['series years'] + 'Present'
            em.set_author(
                name=f"{data['kind']} | {years} | {data['seasons']} Seasons",
                url=url + 'episodes/',
            )
        elif data['kind'].lower() == 'movie':
            log.debug('--- MOVIE ---')
            data['kind'] = 'Movie'
            runtime = f" | {data['runtimes'][0]} min" if 'runtimes' in data else ''
            em.set_author(
                name=f"{data['year']} {data['kind']}{runtime}",
                url=url + 'fullcredits/',
            )
        else:
            log.debug('--- OTHER ---')
            data['kind'] = data['kind'].title()
            em.set_author(
                name=f"{data['kind']} - {data['year']} ",
                url=url + 'fullcredits/',
            )

        title = f"{data['title']}"
        if 'localized title' in data:
            title = f"{data['localized title']}"
        if 'year' in data:
            title += f" ({data['year']})"
        em.title = title
        em.url = url
        lines = [
            f'**Genres:** {genres}',
            f'**Stars:** {cast}\n',
        ]
        if 'plot outline' in data:
            lines.append(data['plot outline'])
        elif 'plot' in data:
            lines.append(data['plot'][0])
        elif 'synopsis' in data:
            lines.append(data['synopsis'][:800])
        if 'videos' in data:
            lines.append(f"\n📺 [Watch Trailer]({data['videos'][0]})")
        em.description = '\n'.join(lines)
        # em.set_image(url=data['full-size cover url'])
        if 'rating' in data and 'votes' in data:
            em.set_footer(text=f"⭐ {data['rating']} of 10 Stars with {data['votes']:,} Ratings on IMDB")
        await ctx.send(embed=em)
