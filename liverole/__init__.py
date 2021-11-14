from .liverole import Liverole


async def setup(bot):
    cog = Liverole(bot)
    bot.add_cog(cog)
    await cog.initialize()
