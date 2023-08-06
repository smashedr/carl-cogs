from .exif import Exif


async def setup(bot):
    cog = Exif(bot)
    await bot.add_cog(cog)
