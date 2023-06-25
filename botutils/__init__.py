from .botutils import Botutils


async def setup(bot):
    cog = Botutils(bot)
    await bot.add_cog(cog)
