from .dictionary import Dictionary


async def setup(bot):
    cog = Dictionary(bot)
    await bot.add_cog(cog)
