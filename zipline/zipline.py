import datetime
import discord
import httpx
import io
import logging
import validators
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
from typing import Optional, Union, Dict, Any, List

from redbot.core import app_commands, commands, Config

log = logging.getLogger('red.zipline')


class Zipline(commands.Cog):
    """Carl's Zipline Cog"""

    amount = 90
    max_types = 6

    type_icons = {
        'image/jpeg': '🖼️',
        'image/png': '🖼️',
        'image/gif': '🖼️',
        'application/pdf': '📄',
        'application/msword': '📄',
        'application/vnd.ms-powerpoint': '📄',
        'application/vnd.ms-excel': '📄',
        'text/plain': '📄',
        'audio/mpeg': '🎵',
        'audio/wav': '🎵',
        'audio/ogg': '🎵',
        'video/mp4': '🎥',
        'video/mpeg': '🎥',
        'application/zip': '📦',
        'application/x-rar-compressed': '📦',
        'application/x-tar': '📦',
        'application/gzip': '📦',
        'application/json': '📋',
        'application/xml': '📋',
        'application/javascript': '📋',
        'text/html': '📋',
        'text/css': '📋',
        'text/csv': '📋',
        'text/xml': '📋',
        'application/sql': '📋',
        'application/x-python': '🐍',
        'application/octet-stream': '⬇️',
    }

    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }

    user_default = {
        'base_url': None,
        'zip_token': None,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_user(**self.user_default)
        self.url: Optional[str] = None
        self.upload_to_zipline = discord.app_commands.ContextMenu(
            name="Upload to Zipline",
            callback=self.upload_to_zipline_callback,
            type=discord.AppCommandType.message,
        )

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data = await self.bot.get_shared_api_tokens('api')
        if data and 'url' in data:
            self.url = data['url'].rstrip('/') + '/plotly/'
        log.info('%s: URL: %s', self.__cog_name__, self.url)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    async def upload_to_zipline_callback(self, interaction, message: discord.Message):
        user: discord.User = interaction.user
        # ctx = await self.bot.get_context(interaction)
        # await ctx.defer(ephemeral=True, thinking=False)
        await interaction.response.defer()
        user_conf: Dict[str, Any] = await self.config.user(user).all()
        log.debug('user_conf: %s', user_conf)
        if not user_conf['base_url'] or not user_conf['zip_token']:
            view = ModalView(self)
            msg = ('❌ You are missing Zipline details. '
                   'Click the button to set Zipline URL and Token.')
            return await interaction.response.send_message(msg, view=view, ephemeral=True, delete_after=300,
                                                           allowed_mentions=discord.AllowedMentions.none())

        if message.attachments:
            log.debug('FILE ATTACHMENT FOUND')
            # files = []
            # for attachment in message.attachments:
            #     files.append(await attachment.to_file())
            msg = 'File Attachment Found - WIP'
            return await interaction.response.send_message(msg, ephemeral=True, delete_after=15,
                                                           allowed_mentions=discord.AllowedMentions.none())

        if message.embeds:
            embeds: List[discord.Embed] = [e for e in message.embeds if e.type == 'rich']
            images = []
            if embeds:
                for embed in embeds:
                    if embed.image:
                        images.append(embed.image)
            if images:
                log.debug('EMBED IMAGE FOUND')
                msg = 'Embed Image Found - WIP'
                return await interaction.response.send_message(msg, ephemeral=True, delete_after=15,
                                                               allowed_mentions=discord.AllowedMentions.none())
        if validators.url(message.content.strip('<>')):
            url = message.content.strip('<>')
            log.debug('URL FOUND')
            msg = 'URL Found - WIP'
            return await interaction.response.send_message(msg, ephemeral=True, delete_after=15,
                                                           allowed_mentions=discord.AllowedMentions.none())

        if message.content:
            log.debug('MESSAGE CONTENT FOUND')
            content = message.content.strip('`')
            msg = 'Message Content Found - WIP'
            return await interaction.response.send_message(msg, ephemeral=True, delete_after=15,
                                                           allowed_mentions=discord.AllowedMentions.none())

        log.debug('NOTHING FOUND')
        msg = 'Nothing Found - WIP (or done)'
        return await interaction.response.send_message(msg, ephemeral=True, delete_after=15,
                                                       allowed_mentions=discord.AllowedMentions.none())

    @commands.hybrid_command(name='zipline', aliases=['zip'])
    @commands.guild_only()
    @app_commands.describe(user='Optional User to get Zipline Stats for')
    async def zip_command(self, ctx: commands.Context, user: Optional[Union[discord.Member, discord.User]] = None):
        """Zipline Command: WIP"""
        await ctx.typing()
        user = user or ctx.author
        user_conf: Dict[str, Any] = await self.config.user(user).all()
        log.debug('user_conf: %s', user_conf)
        if not user_conf['base_url'] or not user_conf['zip_token']:
            view = ModalView(self)
            msg = (f'❌ {user.mention} is missing Zipline details. '
                   f'Click the button to set Zipline URL and Token.')
            return await ctx.send(msg, view=view, ephemeral=True, delete_after=300,
                                  allowed_mentions=discord.AllowedMentions.none())
        stats: List[dict] = await self.get_stats(user_conf['base_url'], user_conf['zip_token'])
        data: Dict[str, Any] = stats[0]['data']
        log.debug('data: %s', data)
        short_url = user_conf['base_url'].split('//')[1]
        embed = discord.Embed(
            title=short_url,
            url=user_conf['base_url'],
            timestamp=datetime.datetime.strptime(stats[0]['createdAt'], "%Y-%m-%dT%H:%M:%S.%fZ"),
            color=discord.Colour.random(),
        )
        embed.add_field(name='Files', value=data['count'])
        embed.add_field(name='Size', value=data['size'])
        embed.add_field(name='Views', value=data['views_count'])
        lines = []
        i = 0
        for i, count in enumerate(data['types_count'], 1):
            if i > self.max_types:
                break
            icon = self.type_icons.get(count['mimetype'], '❔')
            lines.append(f"**{count['count']}** `{count['mimetype']}` {icon}")
        file_types = '\n'.join(lines)
        embed.description = (
            f"**Top {i-1} Types**\n\n"
            f"{file_types}\n\n**Overall Stats**"
        )
        # embed.set_author(name=user.display_name, icon_url=user.avatar.url, url=user_conf['base_url'])
        embed.set_footer(text=f"{user.display_name}'s Zipline Stats", icon_url=user.avatar.url)

        graph = self.gen_graph_fig(stats)
        pie = self.gen_pie_fig(stats)
        if self.url:
            graph_html = graph.to_html(include_plotlyjs='cdn', config={'displaylogo': False})
            graph_href = await self.post_data(graph_html)
            pie_html = pie.to_html(include_plotlyjs='cdn', config={'displaylogo': False})
            pie_href = await self.post_data(pie_html)
            log.debug('graph_href: %s', graph_href)
            log.debug('pie_href: %s', pie_href)
            if pie_href:
                embed.description += f'\n[View Interactive Pie Chart...]({self.url}{pie_href})'
            if graph_href:
                embed.description += f'\n[View Interactive Graph...]({self.url}{graph_href})'

        ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        files = []
        for name, figure in [('graph', graph), ('pie', pie)]:
            file = io.BytesIO()
            file.write(figure.to_image())
            file.seek(0)
            files.append(discord.File(file, f"{short_url}-{name}-{ts}.png"))

        embed.set_thumbnail(url=f"attachment://{short_url}-pie-{ts}.png")
        embed.set_image(url=f"attachment://{short_url}-graph-{ts}.png")
        content = 'New Zipline CLI ⭐ <https://github.com/cssnr/zipline-cli>'
        await ctx.send(content=content, files=files, embed=embed, allowed_mentions=discord.AllowedMentions.none())

    async def get_stats(self, url, token: str) -> List[dict]:
        return await self._get_json(url + '/api/stats', token, amount=self.amount)

    async def _get_json(self, url: str, token: str, **kwargs) -> Any:
        async with httpx.AsyncClient(**self.http_options) as client:
            headers = {'Authorization': token}
            r = await client.get(url, headers=headers, params=kwargs)
            r.raise_for_status()
            return r.json()

    async def post_data(self, html: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.post(url=self.url, content=html)
                log.debug('r.status_code: %s', r.status_code)
                r.raise_for_status()
                return r.text
        except Exception as error:
            log.debug(error)
            return None

    @staticmethod
    def gen_pie_fig(stats: List[dict]) -> go.Figure:
        # Gen Plotly Data
        data: List[dict] = stats[0]['data']['types_count']
        mimetype, count = [], []
        for mime in data:
            mimetype.append(mime['mimetype'])
            count.append(mime['count'])

        df = {'File Types': mimetype, 'Count': count}
        pio.templates.default = 'plotly_dark'
        title = f"{len(data)} Types in {stats[0]['data']['count']} Files at {stats[0]['data']['size']}"
        fig = px.pie(df, values='Count', names='File Types', title=title)
        return fig

    @staticmethod
    def gen_graph_fig(stats: List[dict]) -> go.Figure:
        dates, files, views = [], [], []
        for stat in reversed(stats):
            dates.append(stat['createdAt'])
            files.append(stat['data']['count'])
            views.append(stat['data']['views_count'])
        lines = [('Files', files), ('Views', views)]
        pio.templates.default = "plotly_dark"
        fig = go.Figure()
        for name, data in lines:
            fig.add_trace(go.Scatter(x=dates, y=data, name=name))
        fig.update_layout(xaxis_title='Date', yaxis_title='Count')
        return fig

    # @staticmethod
    # def _bitsize(number: Union[int, float]) -> str:
    #     for unit in ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]:
    #         if abs(number) < 1000.0:
    #             return "{0:.1f}{1}".format(number, unit)
    #         number /= 1000.0
    #     return "{0:.1f}{1}".format(number, "YB")


class ModalView(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label='Set Zipline Details', style=discord.ButtonStyle.blurple, emoji='🖼️')
    async def set_grafana(self, interaction, button):
        log.debug(interaction)
        log.debug(button)
        modal = DataModal(view=self)
        await interaction.response.send_modal(modal)


class DataModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View):
        super().__init__(title='Set Zipline Details')
        self.view = view
        self.base_url = discord.ui.TextInput(
            label='Zipline Base URL',
            placeholder='https://i.cssnr.com/',
            style=discord.TextStyle.short,
            max_length=255,
            min_length=10,
        )
        self.add_item(self.base_url)
        self.zip_token = discord.ui.TextInput(
            label='Zipline Authorization Token',
            placeholder='alRLdlKDFJ31FckdfjEndu5n.AL4nxkdkMjerLqMAPA',
            style=discord.TextStyle.short,
            max_length=43,
            min_length=43,
        )
        self.add_item(self.zip_token)

    async def on_submit(self, interaction: discord.Interaction):
        # discord.interactions.InteractionResponse
        log.debug('ReplyModal - on_submit')
        # message: discord.Message = interaction.message
        user: discord.Member = interaction.user
        # user_conf: Dict[str, str] = await self.view.cog.config.user(user).all()
        # log.debug('self.base_url.value: %s', self.base_url.value)
        # log.debug('self.zip_token.value: %s', self.zip_token.value)
        # TODO: Verify Settings Here
        user_conf = {
            'base_url': self.base_url.value.strip('/ '),
            'zip_token': self.zip_token.value.strip(),
        }
        await self.view.cog.config.user(user).set(user_conf)
        log.debug(user_conf)
        msg = "✅ Zipline Details Updated Successfully..."
        await interaction.response.send_message(msg, ephemeral=True)
