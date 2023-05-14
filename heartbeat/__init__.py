from .heartbeat import Heartbeat


async def setup(bot):
    cog = Heartbeat(bot)
    await bot.add_cog(cog)
    # await cog.post_init()
