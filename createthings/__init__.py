from .createthings import Createthings


async def setup(bot):
    cog = Createthings(bot)
    await bot.add_cog(cog)
