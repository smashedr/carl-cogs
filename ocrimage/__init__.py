from .ocrimage import Ocrimage


async def setup(bot):
    cog = Ocrimage(bot)
    await bot.add_cog(cog)
