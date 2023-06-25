from .consolecmds import Consolecmds


async def setup(bot):
    cog = Consolecmds(bot)
    await bot.add_cog(cog)
