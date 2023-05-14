from .chatgpt import Chatgpt


async def setup(bot):
    cog = Chatgpt(bot)
    await bot.add_cog(cog)
