from .youtube import YouTube


async def setup(bot):
    cog = YouTube(bot)
    await bot.add_cog(cog)
