from .carlcog import Carlcog


async def setup(bot):
    cog = Carlcog(bot)
    bot.add_cog(cog)
    await cog.initialize()
