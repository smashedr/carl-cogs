from .autoroles import Autoroles


async def setup(bot):
    cog = Autoroles(bot)
    await bot.add_cog(cog)
