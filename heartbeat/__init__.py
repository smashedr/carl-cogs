from .heartbeat import Heartbeat


async def setup(bot):
    cog = Heartbeat(bot)
    bot.add_cog(cog)
    cog.post_init()
