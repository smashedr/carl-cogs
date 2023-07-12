import datetime
import discord
import logging
from typing import Any, Dict, Optional
from uptime_kuma_api import UptimeKumaApi

from redbot.core import app_commands, commands, Config
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.uptimekuma')


class Uptimekuma(commands.Cog):
    """Carl's Uptimekuma Cog"""

    statuses = {
        0: {
            'name': 'DOWN',
            'icon': '⛔',
        },
        1: {
            'name': 'Up',
            'icon': '✅',
        },
        2: {
            'name': 'Pending',
            'icon': '⌛',
        },
        3: {
            'name': 'in Maintenance',
            'icon': '⚠️',
        },
    }

    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }

    user_default = {
        'kumas': {},
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_user(**self.user_default)
        self.current: Optional[datetime.datetime] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        # self.check_kuma.start()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        # self.check_kuma.cancel()

    # @tasks.loop(minutes=5.0)
    # async def check_kuma(self):
    #     log.info('%s: Check Kuma Task', self.__cog_name__)
    #     self.current = datetime.datetime.now()
    #     log.info('Hour: %s Sec: %s', self.current.hour, self.current.second)
    #     all_users: Dict[int, dict] = await self.config.all_users()
    #     async for user_id, data in AsyncIter(all_users.items(), delay=5, steps=10):
    #         if not data['kuma']:
    #             log.debug('No Kuma for user: %s', user_id)
    #             continue

    @commands.hybrid_group(name='kuma', aliases=['uptimekuma'])
    @commands.guild_only()
    async def _kuma(self, ctx: commands.Context):
        """Uptimekuma Command"""

    @_kuma.command(name='list', aliases=['instances'])
    @commands.guild_only()
    async def _kuma_list(self, ctx: commands.Context):
        """List all Uptime Kuma Instances."""
        kumas: Dict[str, Any] = await self.config.user(ctx.author).kumas()
        if not kumas:
            view = ModalView(self)
            content = '⛔ No Uptime Kuma Instances Found. Add some first...'
            return await view.send_initial_message(ctx, content)
        lines = [f'🆙 Uptime Kuma Instances: `{len(kumas)}`']
        for name, kuma in kumas.items():
            lines.append(f"**{name}:** <{kuma['url']}>")
        await ctx.send('\n'.join(lines))

    @_kuma.command(name='add', aliases=['new', 'set', 'setup'])
    @commands.guild_only()
    async def _kuma_add(self, ctx: commands.Context):
        """Add UptimeKuma Instance."""
        # kumas: Dict[str, Any] = await self.config.user(ctx.author).kumas()
        view = ModalView(self)
        content = 'Click the button to add an UptimeKuma instance.'
        await view.send_initial_message(ctx, content)

    @_kuma.command(name='status', aliases=['show'])
    @commands.guild_only()
    @app_commands.describe(name='Name of the UptimeKuma instance')
    async def _kuma_status(self, ctx: commands.Context, name: Optional[str]):
        """Get Status of an UptimeKuma Instance."""
        kumas: Dict[str, Any] = await self.config.user(ctx.author).kumas()
        if not kumas:
            view = ModalView(self)
            content = '⛔ No Kumas Found. Click the Button to add a Kuma'
            return await view.send_initial_message(ctx, content)
        elif len(kumas) == 1:
            kuma = list(kumas.values())[0]
            name = list(kumas.keys())[0]
        elif name.lower() in kumas:
            kuma = kumas[name]
        else:
            available = cf.humanize_list(list(kumas.keys()))
            return await ctx.send(f'⛔ Kuma `{name}` not found. Kumas: {available}')
        log.debug('kuma: %s', kuma)
        with UptimeKumaApi(kuma['url']) as api:
            api.login(kuma['user'], kuma['pass'])
            monitors = api.get_monitors()
            heartbeats = api.get_heartbeats()

        lines = []
        for id_, beats in heartbeats.items():
            log.debug('id: %s', id_)
            monitor = next((x for x in monitors if x['id'] == id_), None)
            if not monitor:
                log.error('Monitor not found: %s, %s, %s', ctx.author.id, kuma, id_)
                continue
            lst = beats[-1]
            log.debug('lst: %s', lst)
            _type = str(monitor['type'].value)
            log.debug('_type: %s', _type)
            if _type == 'group':
                continue
            st = self.statuses[int(lst['status'])]
            msg = f"{lst['msg']}" if lst['msg'] else f"is {st['name']}"
            ms = round(lst['ping'], 1) if lst['ping'] and lst['ping'] % 1 != 0 else lst['ping']
            lines.append(
                f"{st['icon']} **{monitor['name']}** `{ms} ms` {msg}"
            )
        data = '\n'.join(lines)
        content = f"Uptime Kuma Status for `{name}`\n<{kuma['url']}>\n{data}"
        await ctx.send(content)


class ModalView(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        super().__init__(timeout=None)
        self.cog = cog
        # self.data: Dict[str, str] = data
        self.user_id: Optional[int] = None
        self.message: Optional[discord.Message] = None

    async def send_initial_message(self, ctx, content: str, **kwargs) -> discord.Message:
        log.debug('send_initial_message')
        self.user_id = ctx.author.id
        self.message = await ctx.send(content, view=self, **kwargs)
        return self.message

    @discord.ui.button(label='Add UptimeKuma Instance', emoji='🆙', style=discord.ButtonStyle.green)
    async def add_kuma(self, interaction: discord.interactions.Interaction, button: discord.Button):
        log.debug(interaction)
        log.debug(button)
        # user = interaction.user
        # user_config: Dict[str, Any] = await self.cog.config.user(user).all()
        modal = DataModal(view=self)
        await interaction.response.send_modal(modal)


class DataModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View):
        super().__init__(title='Add Uptime Kuma Instance')
        self.view: discord.ui.View = view
        # self.data: Dict[str, Any] = data
        self.kuma_name = discord.ui.TextInput(
            label='UptimeKuma Name (for later reference)',
            placeholder='DowntimePuma',
            # default=self.data.get('kuma_name'),
            style=discord.TextStyle.short,
            min_length=3,
            max_length=32,
        )
        self.add_item(self.kuma_name)
        self.kuma_url = discord.ui.TextInput(
            label='UptimeKuma URL',
            placeholder='https://example.com/dashboard',
            # default=self.data.get('kuma_url'),
            style=discord.TextStyle.short,
            min_length=10,
            max_length=255,
        )
        self.add_item(self.kuma_url)
        self.kuma_user = discord.ui.TextInput(
            label='UptimeKuma Username',
            placeholder='admin',
            # default=self.data.get('kuma_user'),
            style=discord.TextStyle.short,
            min_length=3,
            max_length=64,
        )
        self.add_item(self.kuma_user)
        self.kuma_pass = discord.ui.TextInput(
            label='UptimeKuma Password (input not hidden)',
            placeholder='password1 (the 1 makes it secure)',
            # default=self.data.get('kuma_pass'),
            style=discord.TextStyle.short,
            min_length=6,
            max_length=255,
        )
        self.add_item(self.kuma_pass)

    async def on_submit(self, interaction: discord.Interaction):
        # discord.interactions.InteractionResponse
        log.debug('ReplyModal - on_submit')
        # message: discord.Message = interaction.message
        user: discord.Member = interaction.user
        # TODO: Verify Settings Here
        kuma = await self.view.cog.config.user(user).kumas()
        name = self.kuma_name.value.lower().strip()
        url = self.kuma_url.value.replace('/dashboard', '').replace('/manage-status-page', '').strip('/ ')
        kuma[name] = {
            'url': url,
            'user': self.kuma_user.value,
            'pass': self.kuma_pass.value,
        }
        await self.view.cog.config.user(user).kumas.set(kuma)
        log.debug(kuma)
        msg = "✅ UptimeKuma added. I did not verify any input, best of luck bud..."
        await interaction.response.send_message(msg, ephemeral=True)
