from .timer import Timer


async def setup(bot):
    cog = Timer(bot)
    await bot.add_cog(cog)
