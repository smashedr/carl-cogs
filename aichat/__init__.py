from .aichat import AIChat


async def setup(bot):
    cog = AIChat(bot)
    await bot.add_cog(cog)
