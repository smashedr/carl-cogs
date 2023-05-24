from .miscog import Miscog


async def setup(bot):
    cog = Miscog(bot)
    await bot.add_cog(cog)
