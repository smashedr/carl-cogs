from .openai import OpenAI


async def setup(bot):
    cog = OpenAI(bot)
    await bot.add_cog(cog)
