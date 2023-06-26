import asyncio
import discord
import logging
from typing import Union

from redbot.core import commands, Config

log = logging.getLogger('red.autodisconnect')


class Autodisconnect(commands.Cog):
    """Carl's Autodisconnect Cog"""

    guild_default = {
        'timeout': -1,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.Cog.listener(name='on_voice_state_update')
    async def on_voice_state_update(self, member: discord.Member,
                                    before, after):
        def check(m: discord.Member, b, a):
            return a.channel != m.guild.afk_channel and m == member

        if not after.channel or not member.guild.afk_channel or \
                before.channel == after.channel or \
                after.channel != member.guild.afk_channel:
            return

        timeout = await self.config.guild(member.guild).timeout()
        if timeout < 0:
            return

        try:
            await self.bot.wait_for("voice_state_update", check=check,
                                    timeout=timeout * 60)
        except asyncio.TimeoutError:
            pass
        else:
            return

        await member.move_to(None)

    @commands.command(name='autodisconnect', aliases=['autodc'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def autodisconnect(self, ctx: commands.Context,
                             minutes: Union[int, float, str]):
        """Set Autodisconnect time. Use -1 to disable or 0 for instant."""
        if isinstance(minutes, str):
            if minutes.lower() in ['disable', 'off', 'stop']:
                await self.config.guild(ctx.guild).timeout.set(-1)
                return await ctx.send("Autodisconnect disabled.")
        try:
            minutes = int(minutes)
            await self.config.guild(ctx.guild).timeout.set(minutes)
            await ctx.send(f"Autodisconnect timeout set to **{minutes}** minutes.")
        except Exception as error:
            log.error(error)
            await ctx.send(f"I don't know what to do with: **{minutes}**")
