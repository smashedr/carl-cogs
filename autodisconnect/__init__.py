from .autodisconnect import Autodisconnect


async def setup(bot):
    cog = Autodisconnect(bot)
    bot.add_cog(cog)
    await cog.initialize()
