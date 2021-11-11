from .autorooms import Autorooms


async def setup(bot):
    cog = Autorooms(bot)
    bot.add_cog(cog)
    await cog.initialize()
