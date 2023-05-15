from .captcha import Captcha


async def setup(bot):
    cog = Captcha(bot)
    await bot.add_cog(cog)
