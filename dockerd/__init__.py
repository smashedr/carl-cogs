from .dockerd import Dockerd


async def setup(bot):
    cog = Dockerd(bot)
    await bot.add_cog(cog)
