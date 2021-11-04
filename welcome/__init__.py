from .welcome import Welcome


async def setup(bot):
    cog = Welcome(bot)
    bot.add_cog(cog)
    await cog.initialize()
