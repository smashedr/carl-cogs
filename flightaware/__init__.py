from .flightaware import Flightaware


async def setup(bot):
    cog = Flightaware(bot)
    await bot.add_cog(cog)
