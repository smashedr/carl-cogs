from .generators import Generators


async def setup(bot):
    cog = Generators(bot)
    await bot.add_cog(cog)
