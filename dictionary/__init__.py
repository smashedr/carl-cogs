from .dictionary import Dictionary


async def setup(bot):
    cog = Dictionary(bot)
    bot.add_cog(cog)
    cog.post_init()
