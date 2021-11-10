from .autoroles import Autoroles


async def setup(bot):
    cog = Autoroles(bot)
    bot.add_cog(cog)
    await cog.initialize()
