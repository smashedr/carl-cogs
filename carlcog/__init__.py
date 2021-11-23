from .carlcog import Carlcog


async def setup(bot):
    cog = Carlcog(bot)
    cog.cog_load()
    bot.add_cog(cog)
