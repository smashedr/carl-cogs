from .reactpost import ReactPost


async def setup(bot):
    cog = ReactPost(bot)
    await bot.add_cog(cog)
