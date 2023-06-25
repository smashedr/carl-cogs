from .chatgraph import ChatGraph


async def setup(bot):
    cog = ChatGraph(bot)
    await bot.add_cog(cog)
