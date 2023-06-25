from .activerole import ActiveRole


async def setup(bot):
    cog = ActiveRole(bot)
    await bot.add_cog(cog)
