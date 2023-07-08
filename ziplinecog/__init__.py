from .ziplinecog import Zipline


async def setup(bot):
    cog = Zipline(bot)
    await bot.add_cog(cog)
