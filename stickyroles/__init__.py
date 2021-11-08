from .stickyroles import Stickyroles


async def setup(bot):
    cog = Stickyroles(bot)
    bot.add_cog(cog)
    await cog.initialize()
