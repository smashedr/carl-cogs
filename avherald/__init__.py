from .avherald import AVHerald


async def setup(bot):
    cog = AVHerald(bot)
    await bot.add_cog(cog)
