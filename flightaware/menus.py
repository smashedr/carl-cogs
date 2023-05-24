import discord
import logging

from redbot.core import commands

log = logging.getLogger('red.mycog')


class MenuView(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        self.cog = cog
        super().__init__(timeout=None)
        self.add_item(SetURLButton())


class SetURLButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            emoji='\U0001F517',
            label='Enter API URL',
            style=discord.ButtonStyle.green,
            custom_id='mycog-urlbutton',
        )

    async def callback(self, interaction: discord.Interaction):
        log.debug('BUTTON PRESS CALLBACK')
        tolog = interaction
        log.debug(dir(tolog))
        log.debug(type(tolog))
        log.debug(tolog)
        modal = SetURLModal(view=self.view)
        await interaction.response.send_modal(modal)


class SetURLModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View):
        super().__init__(title="API Web URL")
        self.view = view
        self.reply = discord.ui.TextInput(
            label="URL",
            placeholder="https://example.com/",
            style=discord.TextStyle.short,
            max_length=255,
            min_length=1,
        )
        self.add_item(self.reply)

    async def on_submit(self, interaction: discord.Interaction):
        log.debug('MODAL SUBMIT CALLBACK')
        message = interaction.message
        user = interaction.user

        log.debug('-'*40)
        tolog = interaction
        log.debug(dir(tolog))
        log.debug(type(tolog))
        log.debug(tolog)

        # discord.interactions.InteractionResponse
        log.debug('self.reply.value: %s', self.reply.value)

        msg = 'Your bank is being hacked now! Better luck next time bud...'
        await interaction.response.send_message(msg, ephemeral=True)

        # button.disabled = True # set button.disabled to True to disable the button
        # button.label = "No more pressing!" # change the button's label to something else
        # await interaction.response.edit_message(view=self) # edit the message's view

