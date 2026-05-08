from .gemini import Gemini


async def setup(bot):
    cog = Gemini(bot)
    await bot.add_cog(cog)
