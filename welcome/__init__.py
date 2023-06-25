from .welcome import Welcome


async def setup(bot):
    cog = Welcome(bot)
    await bot.add_cog(cog)
