from .carlcog import Carlcog


async def setup(bot):
    cog = Carlcog(bot)
    await bot.add_cog(cog)
