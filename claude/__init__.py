from .claude import Claude


async def setup(bot):
    cog = Claude(bot)
    await bot.add_cog(cog)
