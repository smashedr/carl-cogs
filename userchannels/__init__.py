from .userchannels import Userchannels


async def setup(bot):
    cog = Userchannels(bot)
    await bot.add_cog(cog)
