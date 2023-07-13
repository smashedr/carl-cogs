from .uptimekuma import Uptimekuma


async def setup(bot):
    cog = Uptimekuma(bot)
    await bot.add_cog(cog)
