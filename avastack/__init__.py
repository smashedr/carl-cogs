from .avastack import Avastack


async def setup(bot):
    cog = Avastack(bot)
    await bot.add_cog(cog)
