from .dayinhistory import DayInHistory


async def setup(bot):
    cog = DayInHistory(bot)
    await bot.add_cog(cog)
