from .autoarchive import Autoarchive


async def setup(bot):
    cog = Autoarchive(bot)
    await bot.add_cog(cog)
