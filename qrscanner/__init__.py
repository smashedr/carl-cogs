from .qrscanner import Qrscanner


async def setup(bot):
    cog = Qrscanner(bot)
    await bot.add_cog(cog)
