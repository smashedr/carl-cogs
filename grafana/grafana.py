import datetime
import discord
import httpx
import io
import logging
import re
from thefuzz import process
from typing import Optional, Union, Tuple, Dict, List, Any

from redbot.core import app_commands, commands, Config
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.grafana')


class Grafana(commands.Cog):
    """Carl's Grafana Cog"""

    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }

    user_default = {
        'base_url': None,
        'org_id': None,
        'graphs': {},
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

    @commands.hybrid_command(name='graph')
    @commands.guild_only()
    @app_commands.describe(user='Option User to get Graphs for',
                           dashboard='Dashboard Name or id/name from URL after /d/',
                           panel='Panel ID from the viewPanel= param in URL',
                           from_time='Time to Show, Examples: 12h, 3d, 1w',)
    async def graph_command(self, ctx: commands.Context,
                            user: Optional[Union[discord.Member, discord.User]] = None,
                            dashboard: Optional[str] = None,
                            panel: Optional[int] = None,
                            from_time: Optional[str] = '1d'):
        """Grafana Graph Command
        dashboard: The Dashboard `id/name` from the URL just after `/d/`
        panel: The Panel ID from the `viewPanel=` URL param when viewing the graph
        from_time: How far back show. Examples: `3d`, `1w` Default: `1d`
        """
        # date: Optional[commands.TimedeltaConverter] = datetime.timedelta(days=1))
        user = user or ctx.author
        user_conf: Dict[str, Any] = await self.config.user(user).all()
        log.debug('user_conf: %s', user_conf)
        if not user_conf['base_url'] or not user_conf['org_id']:
            view = ModalView(self)
            msg = (f'{user.mention} is missing Grafana details. '
                   f'Click the button to set Grafana URL and OrgID.')
            return await ctx.send(msg, view=view, ephemeral=True,
                                  allowed_mentions=discord.AllowedMentions.none())
        if not dashboard and not panel:
            return await ctx.send_help()
        if dashboard and not panel:
            log.debug('dashboard: %s', dashboard)
            log.debug('-'*20)
            name, score = process.extractOne(dashboard, list(user_conf['graphs'].keys()))
            log.debug('name: %s', name)
            log.debug('score: %s', score)
            if not name or score < 40:
                msg = f'⛔  No results found about score 40 for: `{dashboard}`'
                return await ctx.send(msg, ephemeral=True, delete_after=120)
            data = user_conf['graphs'][name]
            dashboard = data['dashboard']
            panel = data['panel']
        log.debug('-'*20)
        log.debug('dashboard: %s', dashboard)
        log.debug('panel: %s', panel)
        log.debug('-'*20)
        match = re.search('([0-9]+)([mhdwMY])', from_time)
        if not match:
            msg = f'⛔ Invalid format for **from_time**. Examples: `12h`, `2d`, `1w`'
            return await ctx.send(msg, ephemeral=True, delete_after=120)
        # from_time = int((datetime.datetime.now() - date).timestamp()) * 1000
        # to_time = int(datetime.datetime.now().timestamp()) * 1000
        async with ctx.typing():
            from_time = 'now-' + str(int(match.group(1))) + str(match.group(2))
            log.debug('from_time: %s', from_time)
            url = f"{user_conf['base_url']}/render/d-solo/{dashboard}"
            log.debug('url: %s', url)
            params = {
                'orgId': user_conf['org_id'],
                'from': from_time,
                'to': 'now',
                'panelId': panel,
                'render': '1',
            }
            log.debug('params: %s', params)
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
            file = discord.File(io.BytesIO(r.content), filename=f'{dashboard}-{panel}-{from_time}.png')
            view_url = f"{user_conf['base_url']}/d/{dashboard}?viewPanel={panel}&from={from_time}&to=now"
            await ctx.send(f'Graph: <{view_url}>', file=file, silent=True)

    @commands.group(name='grafana', aliases=['graphana'])
    async def _grafana(self, ctx):
        """Manage Grafana Options"""

    @_grafana.command(name='add', aliases=['new', 'addgraph'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _grafana_add(self, ctx: commands.Context,
                           dashboard: str, panel: int, name: str):
        """Add Graph to Grafana
        dashboard: The Dashboard `id/name` from the URL just after `/d/`
        panel: The Panel ID from the `viewPanel=` URL param when viewing the graph
        name: Name to call the graph for use with `[p]graph name`
        """
        graphs: Dict[str, Any] = await self.config.user(ctx.author).graphs()
        name = name.lower()
        if name in graphs:
            graph = cf.box(graphs[name])
            return await ctx.send(f'⛔  Graph `{name}` already exists:\n{graph}',
                                  ephemeral=True, delete_after=120)
        graphs[name] = {
            'dashboard': dashboard,
            'panel': panel,
        }
        await self.config.user(ctx.author).graphs.set(graphs)
        graph = cf.box(graphs[name])
        await ctx.send(f'✅  Graph `{name}` added:\n{graph}', ephemeral=True)  # ✅

    @_grafana.command(name='list', aliases=['all', 'show', 'view'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _grafana_list(self, ctx: commands.Context,
                            user: Optional[Union[discord.Member, discord.User]]):
        """List Saved Grafana Graphs"""
        user: Union[discord.Member, discord.User] = user or ctx.author
        graphs: Dict[str, Any] = await self.config.user(user).graphs()
        if not graphs:
            content = f'No graphs found for {user.mention}'
            return await ctx.send(content, ephemeral=True, delete_after=120,
                                  allowed_mentions=discord.AllowedMentions.none())
        graph_list: str = cf.humanize_list(list(graphs.keys()))
        content = f'Graphs for {user.mention}\n{graph_list}'
        await ctx.send(content, ephemeral=True,
                       allowed_mentions=discord.AllowedMentions.none())


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
        msg = '✅  Grafana Details Updated Successfully...'
        await interaction.response.send_message(msg, ephemeral=True)
