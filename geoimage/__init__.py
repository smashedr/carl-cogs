from .geoimage import GeoImage


async def setup(bot):
    cog = GeoImage(bot)
    await bot.add_cog(cog)
