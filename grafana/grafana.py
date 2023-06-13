import datetime
import discord
import httpx
import io
import logging
from typing import Optional, Union, Tuple, Dict, List, Any

from redbot.core import app_commands, commands, Config
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.grafana')


class Grafana(commands.Cog):
    """Carl's Grafana Cog"""

    user_default = {
        'base_url': None,
        'org_id': None,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_user(**self.user_default)

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.hybrid_command(name='grafana', aliases=['graphana', 'graph'])
    @commands.guild_only()
    async def _grafana(self, ctx: commands.Context, dashboard: str, panel: int,
                       date: Optional[commands.TimedeltaConverter] = datetime.timedelta(days=1)):
        """Options for managing Grafana."""
        user_conf: Dict[str, str] = await self.config.user(ctx.author).all()
        if not user_conf['base_url'] or not user_conf['org_id']:
            view = ModalView(self)
            msg = (f'{ctx.author.mention} you are missing some Grafana data. '
                   f'Click the button to set Grafana URL and OrgID.')
            return await ctx.send(msg, view=view,
                                  allowed_mentions=discord.AllowedMentions.none())

        log.debug('user_conf: %s', user_conf)
        url = f"{user_conf['base_url']}/render/d-solo/{dashboard}"
        log.debug('url: %s', url)
        view_url = f"{user_conf['base_url']}/d/{dashboard}?viewPanel={panel}"
        params = {
            'orgId': user_conf['org_id'],
            'from': int((datetime.datetime.now() - date).timestamp()) * 1000,
            'to': int(datetime.datetime.now().timestamp()) * 1000,
            'panelId': panel,
            'render': '1',
        }
        log.debug('url: %s', params)
        async with httpx.AsyncClient() as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
        file = discord.File(io.BytesIO(r.content), filename=f'{dashboard}-{panel}.png')
        content = f'Graph: <{view_url}>'
        await ctx.send(content, file=file)


class ModalView(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label='Set Grafana Details', style=discord.ButtonStyle.blurple, emoji='📊')
    async def set_grafana(self, interaction, button):
        log.debug(interaction)
        log.debug(button)
        modal = DataModal(view=self)
        await interaction.response.send_modal(modal)


class DataModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View):
        super().__init__(title='Set Grafana Details')
        self.view = view
        self.base_url = discord.ui.TextInput(
            label='Grafana Base URL',
            placeholder='https://stats.cssnr.com/',
            style=discord.TextStyle.short,
            max_length=255,
            min_length=10,
        )
        self.add_item(self.base_url)
        self.org_id = discord.ui.TextInput(
            label='Organization ID (orgID)',
            placeholder='1',
            style=discord.TextStyle.short,
            max_length=7,
            min_length=1,
        )
        self.add_item(self.org_id)

    async def on_submit(self, interaction: discord.Interaction):
        # discord.interactions.InteractionResponse
        log.debug('ReplyModal - on_submit')
        message: discord.Message = interaction.message
        user: discord.Member = interaction.user
        # user_conf: Dict[str, str] = await self.view.cog.config.user(user).all()
        log.debug('self.base_url.value: %s', self.base_url.value)
        log.debug('self.org_id.value: %s', self.org_id.value)
        user_conf = {
            'base_url': self.base_url.value.strip('/ '),
            'org_id': self.org_id.value.strip(),
        }
        await self.view.cog.config.user(user).set(user_conf)
        log.debug(user_conf)
        msg = '✅ Grafana Details Updated Successfully...'
        await interaction.response.send_message(msg, ephemeral=True)
