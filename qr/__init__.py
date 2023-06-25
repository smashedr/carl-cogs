from .qr import Qr


async def setup(bot):
    cog = Qr(bot)
    await bot.add_cog(cog)
