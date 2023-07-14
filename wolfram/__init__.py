from .wolfram import Wolfram


async def setup(bot):
    cog = Wolfram(bot)
    await bot.add_cog(cog)
