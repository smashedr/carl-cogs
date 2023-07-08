from .dockercog import Docker


async def setup(bot):
    cog = Docker(bot)
    await bot.add_cog(cog)
