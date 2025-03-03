from .jarvis import Jarvis


async def setup(bot):
    cog = Jarvis(bot)
    await bot.add_cog(cog)
