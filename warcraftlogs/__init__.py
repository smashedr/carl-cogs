from .warcraftlogs import Warcraftlogs


async def setup(bot):
    cog = Warcraftlogs(bot)
    await bot.add_cog(cog)
