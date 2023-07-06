import datetime
import discord
import docker
import logging
from typing import Optional, Union, List

from redbot.core import app_commands, commands, Config
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.dockerd')


class Dockerd(commands.Cog):
    """Carl's Dockerd Cog"""

    # guild_default = {
    #     'enabled': False,
    #     'channels': [],
    # }

    def __init__(self, bot):
        self.bot = bot
        self.color = 1294073
        self.client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        self.settings: Optional[dict] = None
        # self.config = Config.get_conf(self, 1337, True)
        # self.config.register_guild(**self.guild_default)

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        self.settings = await self.bot.get_shared_api_tokens('docker')
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.group(name='docker', aliases=['dock', 'dockerd'])
    @commands.guild_only()
    @commands.admin()
    async def _docker(self, ctx: commands.Context):
        """Docker Commands Group."""

    @_docker.command(name='info', aliases=['i'])
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _docker_info(self, ctx: commands.Context):
        """Get Docker Info"""
        info = self.client.info()
        embed: discord.Embed = self.get_embed(info)

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

        # embed.set_author(name=info['ID'])
        embed.set_author(name='info')

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

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar.url)
        await ctx.send(embed=embed)

    @_docker.command(name='stats', aliases=['s'])
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _docker_stats(self, ctx: commands.Context):
        """Get Docker Stats"""
        # info = self.client.info()
        # containers = self.client.containers.list()
        # embed: discord.Embed = self.get_embed(info)

        # stats = []
        # for container in containers:
        #     stats.append(container.stats(stream=False))

    @_docker.group(name='container', aliases=['c', 'con', 'cont', 'contain'])
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _d_container(self, ctx: commands.Context, limit: Optional[int]):
        """Get Docker Containers"""

    @_d_container.command(name='list', aliases=['l', 'li', 'lis'])
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _d_container_list(self, ctx: commands.Context, limit: Optional[int]):
        """Get Docker Containers"""
        info = self.client.info()
        containers = self.client.containers.list()
        embed: discord.Embed = self.get_embed(info)
        embed.set_author(name='container list')

        lines = ['```diff']
        for cont in containers:
            if cont.status == 'running':
                lines.append(f'+ {cont.name}')
            else:
                lines.append(f'- {cont.name}')
        lines.append('```')
        embed.description = '\n'.join(lines)

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar.url)
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
    #     embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar.url)
    #     await ctx.send(embed=embed)


    def get_embed(self, info: dict) -> discord.Embed:
        embed = discord.Embed(
            title=info['Name'],
            color=discord.Colour(self.color),
            timestamp=datetime.datetime.strptime(info['SystemTime'][:26], '%Y-%m-%dT%H:%M:%S.%f'),
        )
        if 'url' in self.settings:
            embed.url = self.settings['url']
        return embed

    @staticmethod
    def convert_bytes(num_bytes: Union[str, int], decimal: Optional[int] = 1) -> str:
        """
        Converts total bytes to human-readable format.
        Args:
            num_bytes (int): The total number of bytes.
            decimal (int, optional): The number of decimal places in the result. Defaults to 1.
        Returns:
            str: The human-readable string representation of the bytes.
        """
        num_bytes = int(num_bytes)
        suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']

        if num_bytes == 0:
            return '0 B'
        i = 0
        while num_bytes >= 1024 and i < len(suffixes) - 1:
            num_bytes /= 1024
            i += 1
        return f'{num_bytes:.{decimal}f} {suffixes[i]}'

