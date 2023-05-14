from .activerole import Activerole


async def setup(bot):
    cog = Activerole(bot)
    await bot.add_cog(cog)
