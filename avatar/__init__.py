from .avatar import Avatar


async def setup(bot):
    cog = Avatar(bot)
    await bot.add_cog(cog)
