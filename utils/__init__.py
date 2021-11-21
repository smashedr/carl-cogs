from .utils import Utils


async def setup(bot):
    cog = Utils(bot)
    bot.add_cog(cog)
    await cog.initialize()
