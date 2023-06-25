from .asn import AviationSafetyNetwork


async def setup(bot):
    cog = AviationSafetyNetwork(bot)
    await bot.add_cog(cog)
