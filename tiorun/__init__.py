from .tiorun import Tiorun


async def setup(bot):
    cog = Tiorun(bot)
    await bot.add_cog(cog)
