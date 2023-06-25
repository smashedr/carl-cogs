from .voicetext import VoiceText


async def setup(bot):
    cog = VoiceText(bot)
    await bot.add_cog(cog)
