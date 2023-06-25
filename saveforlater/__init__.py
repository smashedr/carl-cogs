from .saveforlater import Saveforlater


async def setup(bot):
    cog = Saveforlater(bot)
    await bot.add_cog(cog)
