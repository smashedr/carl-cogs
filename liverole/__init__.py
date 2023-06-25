from .liverole import Liverole


async def setup(bot):
    cog = Liverole(bot)
    await bot.add_cog(cog)
