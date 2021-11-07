from .autorole import Autorole


async def setup(bot):
    cog = Autorole(bot)
    bot.add_cog(cog)
    await cog.initialize()
