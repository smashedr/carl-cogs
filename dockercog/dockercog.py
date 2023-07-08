import concurrent.futures
import datetime
import discord
import docker
import io
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from zipline import Zipline

from redbot.core import commands, Config

log = logging.getLogger('red.docker')


class Docker(commands.Cog):
    """Carl's Docker Cog"""

    global_default = {
        'docker_url': 'unix://var/run/docker.sock',
        'portainer_url': None,
        'zipline_url': None,
        'zipline_token': None,
        'zipline_expire': '30d',
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(**self.global_default)
        self.client: Optional[docker.DockerClient] = None
        self.client_low: Optional[docker.APIClient] = None
        self.zipline: Optional[Zipline] = None
        self.portainer_url: Optional[str] = None
        self.color = 1294073

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data: Dict[str, str] = await self.config.all()
        log.debug('data: %s', data)
        self.client = docker.DockerClient(base_url=data['docker_url'])
        self.client_low = docker.APIClient(base_url=data['docker_url'])
        if data['portainer_url']:
            self.portainer_url = data['portainer_url']
        if data['zipline_url'] and data['zipline_token']:
            self.zipline = Zipline(
                data['zipline_url'],
                authorization=data['zipline_token'],
                expires_at=data['zipline_expire'],
            )
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.group(name='docker', aliases=['dock', 'dockerd'])
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    async def _docker(self, ctx: commands.Context):
        """Docker"""

    @_docker.command(name='settings', aliases=['set', 'setup'])
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    async def _docker_settings(self, ctx: commands.Context):
        """Docker Settings"""
        data: Dict[str, Any] = await self.config.all()
        view = ModalView(self, data)
        msg = 'Press Button. Set Details. Reload Cog. Buy Yacht...'
        return await ctx.send(msg, view=view, ephemeral=True, delete_after=300,
                              allowed_mentions=discord.AllowedMentions.none())

    @_docker.command(name='info', aliases=['i'])
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    async def _docker_info(self, ctx: commands.Context):
        """Docker Info"""
        await ctx.typing()
        info = self.client.info()
        embed: discord.Embed = self.get_embed(ctx, info)
        embed.set_author(name='docker info')

        embed.description = (
            f"```ini\n"
            f"[OS]:     {info['OperatingSystem']}\n"
            f"[Kernel]: {info['KernelVersion']}\n"
            f"[Root]: {info['DockerRootDir']}\n"
            f"```"
        )
        if info['Swarm']:
            embed.add_field(name='Swarm', value='Yes')
            embed.add_field(name='Nodes', value=info['Swarm']['Nodes'])
            embed.add_field(name='Managers', value=info['Swarm']['Managers'])

        embed.add_field(name='OS Version', value=info['OSVersion'])
        embed.add_field(name='OS Type', value=info['OSType'])
        embed.add_field(name='OS Arch', value=info['Architecture'])

        embed.add_field(name='Docker', value=info['ServerVersion'])
        embed.add_field(name='Memory', value=self.convert_bytes(info['MemTotal']))
        embed.add_field(name='CPUs', value=info['NCPU'])

        embed.add_field(name='Containers', value=f"{info['ContainersRunning']}/{info['Containers']}")
        if info['ContainersPaused']:
            embed.add_field(name='Paused', value=f"{info['ContainersPaused']}")
        if info['ContainersStopped']:
            embed.add_field(name='Stopped', value=f"{info['ContainersStopped']}")

        if info['Images']:
            embed.add_field(name='Images', value=f"{info['Images']}")
        if info['Warnings']:
            embed.add_field(name='Warnings', value=f"{info['Warnings']}")

        await ctx.send(embed=embed)

    @_docker.command(name='stats', aliases=['s'])
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    async def _docker_stats(self, ctx: commands.Context, limit: Optional[int] = 0,
                            sort: Optional[str] = 'mem'):
        """Docker Stats"""
        log.debug('limit: %s', limit)
        log.debug('sort: %s', sort)
        await ctx.typing()
        info: Dict = self.client.info()
        containers: List = self.client.containers.list()
        embed: discord.Embed = self.get_embed(ctx, info)
        embed.set_author(name='docker stats')
        stats: List[Dict] = self.process_stats(containers)
        if sort[:3] in ['nam', 'id']:
            stats = sorted(stats, key=lambda x: x['name'])
        elif sort[:3] == 'cpu':
            stats = sorted(stats, key=lambda x: x['cpu_stats']['cpu_usage']['total_usage'])
            stats.reverse()
        else:
            stats = sorted(stats, key=lambda x: x['memory_stats']['usage'])
            stats.reverse()
        overflow = '\n_{} Containers Not Shown..._'
        lines = []
        async with ctx.typing():
            for i, stat in enumerate(stats, 1):
                name = stat['name'].lstrip('/').split('.')[0][:42]
                mem = self.convert_bytes(stat['memory_stats']['usage'])
                mem_max = self.convert_bytes(stat['memory_stats']['limit'])
                cpu = self.calculate_cpu_percent(stat)
                line = f"{mem}/_{mem_max}_ `{cpu}%` **{name}**"
                if len('\n'.join(lines + [line])) > (4096 - len(overflow) - 10):
                    hidden = len(containers) - len(lines)
                    lines.append(overflow.format(hidden))
                    break
                lines.append(line)
                if limit > 0 and limit == i:
                    break

        embed.description = '\n'.join(lines)
        log.debug('embed.description: %s', embed.description)
        await ctx.send(embed=embed)

    @_docker.group(name='container', aliases=['c', 'cont', 'contain'])
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    async def _d_container(self, ctx: commands.Context):
        """Docker Container"""

    @_d_container.command(name='list', aliases=['l', 'ls'])
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    async def _d_container_list(self, ctx: commands.Context, limit: Optional[int]):
        """Docker Container List"""
        await ctx.typing()
        info = self.client.info()
        containers = self.client.containers.list()
        embed: discord.Embed = self.get_embed(ctx, info)
        embed.set_author(name='docker container list')

        overflow = '\n_{} Containers Not Shown..._'
        lines = ['```diff']
        for cont in containers:
            name = cont.name.split('.')[0]
            if cont.status == 'running':
                line = f'+ {name}'
            else:
                line = f'- {name}'
            if len('\n'.join(lines + [line])) > (4096 - len(overflow) - 10):
                hidden = len(containers) - len(lines)
                lines.append('\n```' + overflow.format(hidden))
                break
            lines.append(line)
        else:
            lines.append('```')

        embed.description = '\n'.join(lines)

        if self.portainer_url:
            embed.url = self.portainer_url + '/docker/containers'
        await ctx.send(embed=embed)

    @_d_container.command(name='info', aliases=['i', 'inspect'])
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    async def _d_container_info(self, ctx: commands.Context, name_or_id: str):
        """Docker Container Info"""
        await ctx.typing()
        log.debug('name_or_id: %s', name_or_id)
        info = self.client.info()
        short_id = self.get_id(name_or_id)
        if not short_id:
            return await ctx.send(f'⛔ Container Name/ID Not Found: `{name_or_id}`')
        container = self.client.containers.get(short_id)

        embed: discord.Embed = self.get_embed(ctx, info)
        embed.set_author(name='docker container info')
        stats = container.stats(stream=False)
        embed.colour, icon = self.get_color_icon(container)

        created = datetime.datetime.strptime(container.attrs['Created'][:26], '%Y-%m-%dT%H:%M:%S.%f')
        created_at = int(created.timestamp())
        started = datetime.datetime.strptime(container.attrs['State']['StartedAt'][:26], '%Y-%m-%dT%H:%M:%S.%f')
        started_at = int(started.timestamp())
        embed.description = (
            f"{icon} **{container.name.split('.', 1)[0]}** `{container.short_id}`\n\n"
            f"_{container.name}_\n"
            f"`{container.id}`\n\n"
            f"**Created:** <t:{created_at}:R> on <t:{created_at}:D>\n"
            f"**Started:** <t:{started_at}:R> on <t:{started_at}:D>\n"
        )

        ini = CodeINI()
        ini.add('Platform', container.attrs['Platform'])
        ini.add('Image', container.attrs['Config']['Image'].split('@', 1)[0])
        ini.add('Path', container.attrs['Path'])
        ini.add('Args', ' '.join(container.attrs['Args']))
        # ini.add('ExposedPorts', container.attrs['Config']['ExposedPorts'])

        embed.description += ini.out()

        if container.attrs['State']['Error']:
            embed._colour = discord.Colour.red()
            embed.description += f"\n🔴 **Error**\n{container.attrs['State']['Error']}"

        mem = self.convert_bytes(stats['memory_stats']['usage'])
        mem_max = self.convert_bytes(stats['memory_stats']['limit'])
        embed.add_field(name='Status', value=container.status)
        embed.add_field(name='Memory', value=f'{mem} / {mem_max}')
        embed.add_field(name='CPU', value=f'{self.calculate_cpu_percent(stats)}%')

        if 'Health' in container.attrs['State']:
            embed.add_field(name='Health', value=container.attrs['State']['Health']['Status'])
            embed.add_field(name='FailStreak', value=container.attrs['State']['Health']['FailingStreak'])
            embed.add_field(name='RestartCount', value=container.attrs['RestartCount'])

        if 'Env' in container.attrs['Config'] and 'TRAEFIK_HOST' in container.attrs['Config']['Env']:
            embed.add_field(name='Traefik Host', value=container.attrs['Config']['Env']['TRAEFIK_HOST'], inline=False)

        if container.attrs['NetworkSettings']['Networks']:
            networks = []
            for network, data in container.attrs['NetworkSettings']['Networks'].items():
                networks.append(f"`{network}`")
            embed.add_field(name='Networks', value=', '.join(networks), inline=False)

        if container.attrs['NetworkSettings']['Ports']:
            ports = []
            for port, data in container.attrs['NetworkSettings']['Ports'].items():
                ports.append(f"`{port}`")
            embed.add_field(name='Ports', value=', '.join(ports), inline=False)

        if container.attrs['HostConfig']['Binds']:
            binds = []
            for bind in container.attrs['HostConfig']['Binds']:
                s = bind.split(':')
                binds.append(f"`{s[0]}` -> `{s[1]}`")
            embed.add_field(name='Bind Mounts', value='\n'.join(binds), inline=False)

        # if container.attrs['Mounts']:
        #     mounts = []
        #     for mount in container.attrs['Mounts']:
        #         rw = 'RW' if mount['RW'] else 'RO'
        #         mounts.append(f"{rw} ({mount['Mode']}) - {mount['Type']} {mount.get('Name', '')}\n"
        #                       f"`{mount['Source']}` -> `{mount['Destination']}`")
        #     embed.add_field(name='Mounts', value='\n'.join(mounts), inline=False)

        if 'Env' in container.attrs['Config']:
            del container.attrs['Config']['Env']
        data = json.dumps(container.attrs, indent=4)
        bytes_io = io.BytesIO(bytes(data, 'utf-8'))

        content, file = None, None
        if self.zipline:
            url = self.zipline.send_file(f'{container.short_id}.json', bytes_io)
            content = url.url
        else:
            file = discord.File(bytes_io, f'{container.short_id}.json')

        if self.portainer_url:
            embed.url = self.portainer_url + f'/docker/containers/{container.id}'
        embed.timestamp = datetime.datetime.strptime(info['SystemTime'][:26], '%Y-%m-%dT%H:%M:%S.%f')
        await ctx.send(content, embed=embed, file=file)

    # @_docker.group(name='stack', aliases=['s', 'st', 'stac'])
    # @commands.guild_only()
    # @commands.max_concurrency(1, commands.BucketType.guild)
    # async def _d_stack(self, ctx: commands.Context, limit: Optional[int]):
    #     """Get Docker Containers"""
    #
    # @_d_stack.command(name='list', aliases=['l', 'li', 'lis'])
    # @commands.guild_only()
    # @commands.max_concurrency(1, commands.BucketType.guild)
    # async def _d_stack_list(self, ctx: commands.Context, limit: Optional[int]):
    #     """Get Docker Stacks"""
    #     info = self.client.info()
    #     containers = self.client.containers.list()
    #     embed: discord.Embed = self.get_embed(info)
    #
    #     lines = ['```diff']
    #     for cont in containers:
    #         if cont.status == 'running':
    #             lines.append(f'+ {cont.name}')
    #         else:
    #             lines.append(f'- {cont.name}')
    #     lines.append('```')
    #     embed.description = '\n'.join(lines)
    #
    #     await ctx.send(embed=embed)

    def get_embed(self, ctx: commands.Context, info: dict) -> discord.Embed:
        embed = discord.Embed(
            title=info['Name'],
            color=discord.Colour(self.color),
            timestamp=datetime.datetime.strptime(info['SystemTime'][:26], '%Y-%m-%dT%H:%M:%S.%f'),
        )
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar.url)
        if self.portainer_url:
            embed.url = self.portainer_url + '/docker/dashboard'
        return embed

    def get_id(self, name, short=True) -> Optional[str]:
        containers = self.client.containers.list()
        for container in containers:
            # TODO: Improve This and Add Search
            if name in container.name + container.id:
                if short:
                    return container.short_id
                else:
                    return container.id
        return None

    @staticmethod
    def calculate_cpu_percent(d, round_to=2):
        cpu_count = d["cpu_stats"]["online_cpus"]
        cpu_percent = 0.0
        cpu_delta = float(d["cpu_stats"]["cpu_usage"]["total_usage"]) - float(d["precpu_stats"]["cpu_usage"]["total_usage"])
        system_delta = float(d["cpu_stats"]["system_cpu_usage"]) - float(d["precpu_stats"]["system_cpu_usage"])
        if system_delta > 0.0:
            cpu_percent = cpu_delta / system_delta * 100.0 * cpu_count
        return round(cpu_percent, round_to)

    @staticmethod
    def process_stats(containers, workers: Optional[int] = 60):
        def get_stats(container):
            return container.stats(stream=False)
        stats = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(get_stats, container) for container in containers]
            for future in concurrent.futures.as_completed(futures):
                data = future.result()
                stats.append(data)
        return stats

    @staticmethod
    def get_color_icon(container) -> Tuple[discord.Color, str]:
        if container.status == 'running':
            return discord.Colour.green(), '🟢'
        elif container.status == 'paused':
            return discord.Colour.yellow(), '🟡'
        else:
            return discord.Colour.red(), '🔴'

    @staticmethod
    def convert_bytes(num_bytes: Union[str, int], decimal: Optional[int] = 0) -> str:
        """
        Converts total bytes to human-readable format.
        Args:
            num_bytes (int): The total number of bytes.
            decimal (int, optional): The number of decimal places in the result. Defaults to 1.
        Returns:
            str: The human-readable string representation of the bytes.
        """
        num_bytes = int(num_bytes)
        suffixes = ['b', 'Kb', 'Mb', 'Gb', 'Tb', 'Pb', 'Eb', 'Zb', 'Yb']
        if num_bytes == 0:
            return '0 b'
        i = 0
        while num_bytes >= 1024 and i < len(suffixes) - 1:
            num_bytes /= 1024
            i += 1
        decimal = 1 if i > 2 and decimal == 0 else decimal
        return f'{num_bytes:.{decimal}f} {suffixes[i]}'


class CodeINI(object):
    def __init__(self):
        self.lines: List[str] = []

    def __str__(self):
        return self.out()

    def add(self, key, value):
        self.lines.append(f'[{key}]: {value}')

    def out(self):
        output = '\n'.join(self.lines)
        return f'```ini\n{output}\n```'


class ModalView(discord.ui.View):
    def __init__(self, cog: commands.Cog, data: Dict[str, str]):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data

    @discord.ui.button(label='Set Docker Details', style=discord.ButtonStyle.blurple, emoji='🐳')
    async def set_docker(self, interaction, button):
        log.debug(interaction)
        log.debug(button)
        modal = DataModal(view=self)
        await interaction.response.send_modal(modal)


class DataModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View):
        super().__init__(title='Set Docker Details')
        self.view = view
        self.docker_url = discord.ui.TextInput(
            label='Docker URL',
            # placeholder=self.view.data['docker_url'],
            default=self.view.data['docker_url'],
            style=discord.TextStyle.short,
            max_length=255,
            min_length=10,
            required=False,
        )
        self.add_item(self.docker_url)

        self.portainer_url = discord.ui.TextInput(
            label='Portainer Full Dashboard URL',
            # placeholder=self.view.data['portainer_url'],
            default=self.view.data['portainer_url'],
            style=discord.TextStyle.short,
            max_length=255,
            min_length=10,
            required=False,
        )
        self.add_item(self.portainer_url)

        # self.portainer_endpoint = discord.ui.TextInput(
        #     label='Portainer Endpoint Number',
        #     # placeholder=self.view.data['portainer_endpoint'],
        #     default=self.view.data['portainer_endpoint'],
        #     style=discord.TextStyle.short,
        #     max_length=4,
        #     min_length=1,
        #     required=False,
        # )
        # self.add_item(self.portainer_endpoint)

        self.zipline_url = discord.ui.TextInput(
            label='Zipline Base URL',
            # placeholder=self.view.data['zipline_url'],
            default=self.view.data['zipline_url'],
            style=discord.TextStyle.short,
            max_length=255,
            min_length=10,
            required=False,
        )
        self.add_item(self.zipline_url)

        self.zipline_token = discord.ui.TextInput(
            label='Zipline Authorization Token',
            # placeholder=self.view.data['zipline_token'],
            default=self.view.data['zipline_token'],
            style=discord.TextStyle.short,
            max_length=43,
            min_length=43,
            required=False,
        )
        self.add_item(self.zipline_token)

        self.zipline_expire = discord.ui.TextInput(
            label='Zipline Expire At',
            # placeholder=self.view.data['zipline_expire'],
            default=self.view.data['zipline_expire'],
            style=discord.TextStyle.short,
            max_length=32,
            min_length=2,
            required=False,
        )
        self.add_item(self.zipline_expire)

    async def on_submit(self, interaction: discord.Interaction):
        log.debug('DataModal - on_submit')
        # message: discord.Message = interaction.message
        # user: discord.Member = interaction.user
        portainer_url = self.portainer_url.value.replace('docker/dashboard', '').strip().rstrip('/')
        zipline_url = self.zipline_url.value.replace('dashboard', '').strip().rstrip('/')
        data = {
            'docker_url': self.docker_url.value.strip(),
            'portainer_url': portainer_url,
            # 'portainer_endpoint': self.portainer_endpoint.value.strip(),
            'zipline_url': zipline_url,
            'zipline_token': self.zipline_token.value.strip(),
            'zipline_expire': self.zipline_expire.value.strip(),
        }
        await self.view.cog.config.set(data)
        log.debug(data)
        msg = "✅ Docker Details Updated Successfully..."
        await interaction.response.send_message(msg, ephemeral=True)

