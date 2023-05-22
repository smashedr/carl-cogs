import discord
import logging
from urllib.parse import urlencode

from redbot.core import commands

log = logging.getLogger('red.captcha')


class VerifyView(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        self.cog = cog
        super().__init__(timeout=None)
        self.add_item(GetURLButton(self.cog))


class GetURLButton(discord.ui.Button):
    def __init__(self, cog: commands.Cog):
        super().__init__(
            emoji='\U0001F517',
            label='Get Verification URL',
            style=discord.ButtonStyle.green,
            custom_id='captcha-url-btn',
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        params = {
            'user': interaction.user.id,
            'guild': interaction.guild.id,
        }
        query_string = urlencode(params)
        url = f'{self.cog.url}/verify/?{query_string}'
        message = f'{interaction.user.mention} Click Here: <{url}>'
        await interaction.response.send_message(message, ephemeral=True,
                                                delete_after=180)
