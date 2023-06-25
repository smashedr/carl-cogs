from .weather import Weather


async def setup(bot):
    cog = Weather(bot)
    await bot.add_cog(cog)
