from .warcraftlogs import Warcraftlogs


async def setup(bot):
    cog = Warcraftlogs(bot)
    bot.add_cog(cog)
    await cog.initialize()
