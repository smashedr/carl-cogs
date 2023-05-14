from .autodisconnect import Autodisconnect


async def setup(bot):
    cog = Autodisconnect(bot)
    await bot.add_cog(cog)
