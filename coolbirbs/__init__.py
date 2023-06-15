from .coolbirbs import Coolbirbs


async def setup(bot):
    cog = Coolbirbs(bot)
    await bot.add_cog(cog)
