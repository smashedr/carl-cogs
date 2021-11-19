from .activerole import Activerole


async def setup(bot):
    cog = Activerole(bot)
    bot.add_cog(cog)
    await cog.initialize()
