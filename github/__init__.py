from .github import Github


async def setup(bot):
    cog = Github(bot)
    await bot.add_cog(cog)
