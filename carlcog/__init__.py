from .mycog import MyCog


async def setup(bot):
    cog = MyCog(bot)
    bot.add_cog(cog)
    await cog.initialize()
