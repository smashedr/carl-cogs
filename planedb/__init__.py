from .planedb import Planedb


async def setup(bot):
    cog = Planedb(bot)
    await bot.add_cog(cog)
