from .grafana import Grafana


async def setup(bot):
    cog = Grafana(bot)
    await bot.add_cog(cog)
