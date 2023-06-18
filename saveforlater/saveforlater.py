import discord
import logging
from typing import List

from redbot.core import commands
from redbot.core.utils import can_user_send_messages_in

log = logging.getLogger('red.saveforlater')


class Saveforlater(commands.Cog):
    """Carl's Saveforlater Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.save_for_later = discord.app_commands.ContextMenu(
            name="Save for Later",
            callback=self.save_for_later_callback,
            type=discord.AppCommandType.message,
        )

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        self.bot.tree.add_command(self.save_for_later)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.bot.tree.remove_command("Save for Later", type=discord.AppCommandType.message)

    async def save_for_later_callback(self, interaction, message: discord.Message):
        # ctx = await self.bot.get_context(interaction)
        # await ctx.defer(ephemeral=True, thinking=False)
        # await interaction.response.defer()
        if not can_user_send_messages_in(interaction.user.guild.me, interaction.user):
            msg = (f'⛔ Unable to send you a Direct Message. '
                   f'Check your privacy settings for the guild and enable Direct Messages.')
            return await interaction.response.send_message(msg, ephemeral=True, delete_after=60)
        files = []
        for attachment in message.attachments:
            files.append(await attachment.to_file())
        embeds: List[discord.Embed] = [e for e in message.embeds if e.type == 'rich']
        content = (f'**Saved Message** from {message.jump_url}\n'
                   f'{message.author.mention}: {message.content}')
        await interaction.user.send(content, embeds=embeds, files=files, silent=True,
                                    allowed_mentions=discord.AllowedMentions.none())
        await interaction.response.send_message('✅ Message Saved in DM for Later.',
                                                ephemeral=True, delete_after=15)
