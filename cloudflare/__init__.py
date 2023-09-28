from .cloudflare import Cloudflare


async def setup(bot):
    cog = Cloudflare(bot)
    await bot.add_cog(cog)
