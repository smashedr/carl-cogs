import concurrent.futures
import datetime
import discord
import docker
import logging
from typing import Optional, Union

from redbot.core import commands

log = logging.getLogger('red.dockerd')


class Dockerd(commands.Cog):
    """Carl's Dockerd Cog"""

    docker_url = 'unix://var/run/docker.sock'

    def __init__(self, bot):
        self.bot = bot
        self.color = 1294073
        self.client = docker.DockerClient(base_url=self.docker_url)
        self.client_low = docker.APIClient(base_url=self.docker_url)
        self.settings: Optional[dict] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        self.settings = await self.bot.get_shared_api_tokens('docker')
        log.info('settings: %s', self.settings)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.group(name='docker', aliases=['dock', 'dockerd'])
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    async def _docker(self, ctx: commands.Context):
        """Docker Commands Group."""

    @_docker.command(name='info', aliases=['i', 'in', 'inf'])
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    async def _docker_info(self, ctx: commands.Context):
        """Get Docker Info"""
        await ctx.typing()
        info = self.client.info()
        embed: discord.Embed = self.get_embed(ctx, info)
        embed.set_author(name='docker info')

        embed.description = (
            f"```ini\n"
            f"[OS]:     {info['OperatingSystem']}\n"
            f"[Kernel]: {info['KernelVersion']}\n"
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
        # embed.add_field(name='Images', value=f"{info['Images']}")
        await ctx.send(embed=embed)

    # @staticmethod
    # async def container_stats(container):
    #     return container.stats(stream=False)

    @staticmethod
    def calculate_cpu_percent(d, round_to=2):
        cpu_count = d["cpu_stats"]["online_cpus"]
        cpu_percent = 0.0
        cpu_delta = float(d["cpu_stats"]["cpu_usage"]["total_usage"]) - float(d["precpu_stats"]["cpu_usage"]["total_usage"])
        system_delta = float(d["cpu_stats"]["system_cpu_usage"]) - float(d["precpu_stats"]["system_cpu_usage"])
        if system_delta > 0.0:
            cpu_percent = cpu_delta / system_delta * 100.0 * cpu_count
        return round(cpu_percent, round_to)

    @_docker.command(name='stats', aliases=['s', 'st', 'sta', 'stat'])
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    async def _docker_stats(self, ctx: commands.Context, limit: Optional[int] = 0,
                            sort: Optional[str] = 'mem'):
        """Get Docker Stats"""
        log.debug('limit: %s', limit)
        log.debug('sort: %s', sort)
        await ctx.typing()
        info = self.client.info()
        containers = self.client.containers.list()
        embed: discord.Embed = self.get_embed(ctx, info)
        embed.set_author(name='docker stats')

        # stats: List[Dict[str, Any]] = []
        # async with ctx.typing():
        #     async for container in AsyncIter(containers, 0.01):
        #         # TODO: This Blocks too Long
        #         # data = self.client_low.stats(container=container.name, stream=False)
        #         data: Dict[str, Any] = container.stats(stream=False)
        #         stats.append(data)

        # async def fetch_container_stats(container) -> Dict[str, Any]:
        #     data: Dict[str, Any] = await self.container_stats(container)
        #     return data
        # tasks = [fetch_container_stats(container) for container in containers]
        # stats = await asyncio.gather(*tasks)

        stats = []

        def get_stats(container):
            data = container.stats(stream=False)
            return data

        def process_stats():
            with concurrent.futures.ThreadPoolExecutor(max_workers=60) as executor:
                futures = [executor.submit(get_stats, container) for container in containers]
                for future in concurrent.futures.as_completed(futures):
                    data = future.result()
                    stats.append(data)

        process_stats()

        if sort[:3] in ['nam', 'id']:
            stats = sorted(stats, key=lambda x: x['name'])
        elif sort[:3] == 'cpu':
            stats = reversed(sorted(stats, key=lambda x: x['cpu_stats']['cpu_usage']['total_usage']))
        else:
            stats = reversed(sorted(stats, key=lambda x: x['memory_stats']['usage']))
        overflow = '\n_{} Containers Not Shown..._'
        lines = []
        async with ctx.typing():
            for i, stat in enumerate(stats, 1):
                name = stat['name'].lstrip('/').split('.')[0][:34]
                mem = self.convert_bytes(stat['memory_stats']['usage'])
                mem_max = self.convert_bytes(stat['memory_stats']['limit'])
                cpu = self.calculate_cpu_percent(stat)
                line = f"{mem}/{mem_max} `{cpu}%` - **{name}**"
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

    @_docker.group(name='container', aliases=['c', 'co' 'con', 'cont', 'contain'])
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    async def _d_container(self, ctx: commands.Context):
        """Get Docker Containers"""

    @_d_container.command(name='list', aliases=['l', 'ls', 'li', 'lis'])
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    async def _d_container_list(self, ctx: commands.Context, limit: Optional[int]):
        """Get Docker Containers"""
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

        await ctx.send(embed=embed)

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
        if 'url' in self.settings:
            embed.url = self.settings['url']
        return embed

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

