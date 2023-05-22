from .pubsub import Pubsub


async def setup(bot):
    cog = Pubsub(bot)
    await bot.add_cog(cog)
