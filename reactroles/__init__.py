from .reactroles import Reactroles


async def setup(bot):
    cog = Reactroles(bot)
    bot.add_cog(cog)
    await cog.initialize()
