from .geotools import GeoTools


async def setup(bot):
    cog = GeoTools(bot)
    await bot.add_cog(cog)
