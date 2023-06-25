from .sunsetrise import Sunsetrise


async def setup(bot):
    cog = Sunsetrise(bot)
    await bot.add_cog(cog)
