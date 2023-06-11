from .avherald import Avherald


async def setup(bot):
    cog = Avherald(bot)
    await bot.add_cog(cog)
