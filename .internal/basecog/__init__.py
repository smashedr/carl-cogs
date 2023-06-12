from .basecog import Basecog


async def setup(bot):
    cog = Basecog(bot)
    await bot.add_cog(cog)
