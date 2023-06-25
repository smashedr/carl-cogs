from .lmgtfy import Lmgtfy


async def setup(bot):
    cog = Lmgtfy(bot)
    await bot.add_cog(cog)
