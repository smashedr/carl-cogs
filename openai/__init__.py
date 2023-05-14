from .openai import Openai


async def setup(bot):
    cog = Openai(bot)
    await bot.add_cog(cog)
