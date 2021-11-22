from .botutils import Botutils


async def setup(bot):
    cog = Botutils(bot)
    bot.add_cog(cog)
    await cog.cog_load()
