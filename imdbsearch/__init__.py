from .imdbsearch import Imdblookup


async def setup(bot):
    cog = Imdblookup(bot)
    await bot.add_cog(cog)
