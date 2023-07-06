from .webtools import Webtools


async def setup(bot):
    cog = Webtools(bot)
    await bot.add_cog(cog)
