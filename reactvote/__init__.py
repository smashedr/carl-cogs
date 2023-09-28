from .reactvote import ReactVote


async def setup(bot):
    cog = ReactVote(bot)
    await bot.add_cog(cog)
