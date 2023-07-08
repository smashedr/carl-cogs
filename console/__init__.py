from .console import Console


async def setup(bot):
    cog = Console(bot)
    await bot.add_cog(cog)
