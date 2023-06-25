from .stickyroles import Stickyroles


async def setup(bot):
    cog = Stickyroles(bot)
    await bot.add_cog(cog)
