from .autochannels import Autochannels


async def setup(bot):
    cog = Autochannels(bot)
    bot.add_cog(cog)
    await cog.initialize()
