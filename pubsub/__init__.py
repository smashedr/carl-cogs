from .pubsub import PubSub


async def setup(bot):
    cog = PubSub(bot)
    await bot.add_cog(cog)
    # await cog.initialize()
