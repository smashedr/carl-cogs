from .reactroles import Reactroles


async def setup(bot):
    cog = Reactroles(bot)
    await bot.add_cog(cog)
