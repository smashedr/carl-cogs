from .createroles import Createroles


async def setup(bot):
    cog = Createroles(bot)
    bot.add_cog(cog)
    await cog.initialize()
