from .createthings import Createthings


async def setup(bot):
    cog = Createthings(bot)
    bot.add_cog(cog)
    await cog.initialize()
