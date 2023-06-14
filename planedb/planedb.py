import discord
import datetime
import httpx
import json
import logging
import re
from bs4 import BeautifulSoup
from thefuzz import process
from typing import Optional, Union, Tuple, Dict, List, Any
import redis.asyncio as redis

from redbot.core import app_commands, commands, Config
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.planedb')


class Planedb(commands.Cog):
    """Carl's Planedb Cog"""

    http_options = {
        'follow_redirects': True,
        'timeout': 30,
    }
    chrome_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/113.0.0.0 Safari/537.36')
    headers = {'user-agent': chrome_agent}

    global_default = {
        'planes': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(**self.global_default)
        self.redis: Optional[redis.Redis] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data: dict = await self.bot.get_shared_api_tokens('redis')
        self.redis = redis.Redis(
            host=data['host'] if 'host' in data else 'redis',
            port=int(data['port']) if 'port' in data else 6379,
            db=int(data['db']) if 'db' in data else 0,
            password=data['pass'] if 'pass' in data else None,
        )
        await self.redis.ping()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.hybrid_group(name='plane', aliases=['planedb'])
    @commands.guild_only()
    async def _planedb(self, ctx: commands.Context):
        """Planedb Command"""

    @_planedb.command(name='search', aliases=['s', 'find', 'lookup'],
                      description='Search Plane by Name')
    @app_commands.describe(name='Name of the Resource')
    @commands.guild_only()
    async def _planedb_search(self, ctx: commands.Context, *, name: str):
        """Search Plane by Name"""
        name = name.lower().strip()
        log.debug('name: %s', name)
        planes: List[Dict[str, str]] = await self.config.planes()
        log.debug('planes: %s', planes)
        names = [x['name'] for x in planes]
        log.debug('names: %s', names)
        results: List[Tuple] = process.extract(name, names, limit=5)
        log.debug('results: %s', results)
        if not results:
            return await ctx.send(f"⛔  No Planes found for: {name}",
                                  ephemeral=True, delete_after=60)
        if len(results) == 1:
            result = results[0][0]
            log.debug('result: %s', result)
            plane = next((x for x in planes if x['name'] == result), None)
            log.debug('plane: %s', plane)
        else:
            # TODO: Send Planes and wait_for Selection
            plane = None
            return await ctx.send(f"⛔  WIP: Multiple Planes Found For: {name}",
                                  ephemeral=True, delete_after=60)
        if not plane:
            return await ctx.send(f"⛔  BUG: Plane Matched but Not Found: {name}",
                                  ephemeral=True, delete_after=60)
        content = (
            f"✅  Plane Found: {plane['name']} - "
            f"{plane['registration']} - "
            f"{plane['icao_hex']}"
        )
        plane_photo = await self.get_jet_photo(plane['registration'])
        if plane_photo:
            content += f'\n{plane_photo}'
        await ctx.send(content, ephemeral=True)

    @_planedb.command(name='add', aliases=['a', 'new'],
                      description='Add a Plane to Plane DB')
    @app_commands.describe(registration='Aircraft Registration Number',
                           icao_hex='24-bit ICAO Hex for ADS-B',
                           name='Name of the Resource')
    @commands.guild_only()
    async def _planedb_add(self, ctx: commands.Context, registration: str, icao_hex: str, *, name: str):
        """Add a Plane to Plane DB"""
        # https://www.avionictools.com/icao.php
        name = name.lower().strip()
        log.debug('name: %s', name)
        planes: List[Dict[str, str]] = await self.config.planes()
        log.debug('planes: %s', planes)
        plane = next((x for x in planes if x['name'] == name), None)
        if plane:
            return await ctx.send(f"⛔  Plane found for name: {name} - {plane['registration']}",
                                  ephemeral=True, delete_after=60)
        m = re.search('[A-Z0-9-]{3,7}', registration.upper())
        if not m or not m.group(0):
            return await ctx.send(f'⛔  Unable to validate registration: {registration}',
                                  ephemeral=True, delete_after=60)
        registration = m.group(0)
        log.debug('registration: %s', registration)

        m = re.search('^[a-fA-F0-9]{6}$', icao_hex.lower())
        if not m or not m.group(0):
            return await ctx.send(f'⛔  Unable to validate registration: {registration}',
                                  ephemeral=True, delete_after=60)
        icao_hex = m.group(0)
        log.debug('icao_hex: %s', icao_hex)
        plane = {
            'name': name,
            'registration': registration,
            'icao_hex': icao_hex,
        }
        log.debug('plane: %s', plane)
        planes.append(plane)
        await self.config.planes.set(planes)
        await ctx.send(f"✅  Plane Added: {plane['name']} - {plane['registration']}",
                       ephemeral=True)

    async def get_jet_photo(self, registration: str) -> Optional[str]:
        base_url = 'https://www.jetphotos.com'
        url = f'{base_url}/photo/keyword/{registration}'
        log.debug('url: %s', url)
        search = await self._get_cache_req(url)
        soup = BeautifulSoup(search, 'html.parser')
        first_photo = soup.find('a', class_='result__photoLink')
        if not first_photo:
            return None
        log.debug('first_photo: %s', first_photo['href'])
        url = f"{base_url}{first_photo['href']}"
        log.debug('url: %s', url)
        result = await self._get_cache_req(url)
        soup = BeautifulSoup(result, 'html.parser')
        large_photo = soup.find('img', class_='large-photo__img')
        if not large_photo:
            return None
        log.debug('large_photo: %s', large_photo)
        log.debug('large_photo: %s', large_photo['srcset'])
        return f"{large_photo['srcset']}"

    async def _get_cache_req(self, url: str,
                             minutes: Optional[int] = 60*24*7,
                             headers: Optional[dict] = None,
                             http_options: Optional[dict] = None,
                             **kwargs) -> str:
        data: str = await self.redis.get(url)
        if data:
            log.debug('--- CACHE CALL ---')
            return data
        log.debug('--- remote call ---')
        http_options = {
                           'follow_redirects': True,
                           'timeout': 30,
                       } or http_options
        chrome_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/113.0.0.0 Safari/537.36'
        )
        headers = {'user-agent': chrome_agent} or headers
        async with httpx.AsyncClient(**http_options) as client:
            r = await client.get(url, headers=headers, **kwargs)
            r.raise_for_status()
        log.debug('--- cache set ---')
        await self.redis.setex(url, datetime.timedelta(minutes=minutes), r.text)
        return r.text
