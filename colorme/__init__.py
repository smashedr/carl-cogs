from .colorme import ColorMe


async def setup(bot):
    cog = ColorMe(bot)
    await bot.add_cog(cog)
