from .autochannels import Autochannels


async def setup(bot):
    cog = Autochannels(bot)
    await bot.add_cog(cog)
