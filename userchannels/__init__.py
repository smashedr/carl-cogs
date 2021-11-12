from .userchannels import Userchannels


async def setup(bot):
    cog = Userchannels(bot)
    bot.add_cog(cog)
    await cog.initialize()
