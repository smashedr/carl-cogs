import discord
import logging
import re

from rapidfuzz import process
from typing import List, Union
from unidecode import unidecode

from discord.ext.commands.converter import IDConverter, _get_from_guilds
from discord.ext.commands import errors
from redbot.core import commands

logger = logging.getLogger('red.botutils')


class CarlRoleConverter(IDConverter):
    """Converts to a :class:`~discord.Role`."""

    async def convert(self, ctx, argument) -> discord.Role:
        if not ctx.guild:
            raise errors.NoPrivateMessage()

        id_match = self._get_id_match(argument) or re.match(r'<@&([0-9]+)>$', argument)
        if id_match:
            role = ctx.guild.get_role(int(id_match.group(1)))
            if role:
                return role

        role = discord.utils.get(ctx.guild.roles, name=argument)
        if role:
            return role

        role = discord.utils.find(lambda r: r.name.lower() == str(argument).lower(), ctx.guild.roles)
        if role:
            return role

        raise errors.BadArgument(f'Role "{argument}" not found')


class CarlChannelConverter(IDConverter):
    """This is to convert ID's from a category, voice, or text channel via ID's or names"""

    async def convert(self, ctx: commands.Context, argument: str) -> Union[
                discord.TextChannel, discord.CategoryChannel, discord.VoiceChannel, discord.StageChannel]:
        if not ctx.guild:
            raise errors.NoPrivateMessage()

        id_match = self._get_id_match(argument) or re.match(r"<#([0-9]+)>$", argument)
        if id_match:
            channel = ctx.guild.get_channel(int(id_match.group(1)))
            if channel:
                return channel

        channel = discord.utils.get(ctx.guild.channels, name=argument)
        if channel:
            return channel

        channel = discord.utils.find(lambda r: r.name.lower() == str(argument).lower(), ctx.guild.channels)
        if channel:
            return channel

        raise errors.BadArgument(f'Channel "{argument}" not found')


class FuzzyMember(IDConverter):
    """
    This will accept user ID's, mentions, and perform a fuzzy search for
    members within the guild and return a list of member objects
    matching partial names

    Guidance code on how to do this from:
    https://github.com/Rapptz/discord.py/blob/rewrite/discord/ext/commands/converter.py#L85
    https://github.com/Cog-Creators/Red-DiscordBot/blob/V3/develop/redbot/cogs/mod/mod.py#L24
    """

    async def convert(self, ctx: commands.Context, argument: str) -> List[discord.Member]:
        bot = ctx.bot
        match = self._get_id_match(argument) or re.match(r"<@!?([0-9]+)>$", argument)
        guild = ctx.guild
        result = []
        if match is None:
            # Not a mention
            if guild:
                for m in process.extract(
                    argument,
                    {m: unidecode(m.name) for m in guild.members},
                    limit=None,
                    score_cutoff=75,
                ):
                    result.append(m[2])
                for m in process.extract(
                    argument,
                    {m: unidecode(m.nick) for m in guild.members if m.nick and m not in result},
                    limit=None,
                    score_cutoff=75,
                ):
                    result.append(m[2])
        else:
            user_id = int(match.group(1))
            if guild:
                result.append(guild.get_member(user_id))
            else:
                result.append(_get_from_guilds(bot, "get_member", user_id))

        if not result or result == [None]:
            raise errors.BadArgument('Member "{}" not found'.format(argument))

        return result
