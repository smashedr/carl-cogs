import datetime
import discord
import httpx
import ipaddress
import logging
import socket
import sys
import re
import random
import string
from io import StringIO
from typing import Optional, Dict, Any

from redbot.core import commands
from redbot.core.utils import chat_formatting as cf

from .functions import verbose_ping

log = logging.getLogger('red.consolecmds')


class Consolecmds(commands.Cog):
    """Carl's Consolecmds Cog"""

    ip_urls = {
        'IPLocation': 'https://iplocation.io/ip/{ip}',
        'WhatIS MyIPAddress': 'https://whatismyipaddress.com/ip/{ip}',
        'WHOIS IPLocation': 'https://iplocation.io/ip-whois-lookup/{ip}',
        'WHOIS DNSChecker': 'https://dnschecker.org/ip-whois-lookup.php?query={ip}',
        'WHOIS ARIN': 'https://search.arin.net/rdap/?query={ip}',
    }

    http_options = {
        'follow_redirects': False,
        'timeout': 6,
    }

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    # @commands.Cog.listener(name='on_message_without_command')
    # async def on_message_without_command(self, message: discord.Message):
    #     """Listens for Messages"""
    #     guild: discord.Guild = message.guild
    #     if message.author.bot or not message.attachments or not guild:
    #         return
    #     enabled: bool = await self.config.guild(guild).enabled()
    #     if not enabled:
    #         return
    #     channels: List[int] = await self.config.guild(guild).channels()
    #     if message.channel.id in channels:
    #         return
    #     # run code here

    @commands.command(name='echo', aliases=['print', 'println'])
    async def echo_command(self, ctx: commands.Context, *, echo_string: str):
        await ctx.send(echo_string, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name='rand', aliases=['random'])
    async def rand_command(self, ctx: commands.Context, string_length: Optional[int] = 24,
                           number_of_strings: Optional[int] = 1):
        passwords = []
        for _ in range(number_of_strings):
            choices = (string.ascii_uppercase + string.ascii_lowercase + string.digits)
            for char in 'iIlLoO01':
                choices = choices.replace(char, '')
            passwords.append(''.join(random.choice(choices) for _ in range(string_length)))
        content = cf.box('\n'.join(passwords))
        await ctx.send(content, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name='host', aliases=['nslookup'])
    async def host_command(self, ctx: commands.Context, hostname: str):
        await ctx.typing()
        hostname = hostname.strip('`*')
        try:
            if re.match(r'^([0-9]{1,3}\.){3}[0-9]{1,3}$', hostname):
                result, _, _ = socket.gethostbyaddr(hostname)
            else:
                result = socket.gethostbyname(hostname)
            if result:
                await ctx.send(f'**{hostname}:** `{result}`')
            else:
                await ctx.send(f'⛔ No result for: `{hostname}:`')
        except Exception as error:
            log.error(error)
            await ctx.send(f'⛔ Error: `{error}`')

    @commands.command(name='ping')
    async def ping_command(self, ctx: commands.Context, hostname: str):
        await ctx.typing()
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = StringIO()
            await verbose_ping(hostname, timeout=2)
            sys.stdout = old_stdout
            value = mystdout.getvalue()
            await ctx.send(cf.box(text=value))
        except Exception as error:
            log.error(error)
            await ctx.send(f'⛔ Error: `{error}`')

    @commands.command(name='curl', aliases=['wget'])
    async def curl_command(self, ctx: commands.Context, url: str):
        await ctx.typing()
        if not re.search(r'^[a-zA-Z]+://', url):
            url = 'https://' + url
        try:
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url)
        except Exception as error:
            log.error(error)
            return await ctx.send(f'⛔ Error: `{error}`')
        if 100 <= r.status_code <= 399:
            color = discord.Color.green()
            status = f'✅ {r.status_code}'
            try:
                text = cf.box(r.json()[:2020], lang='json')
            except Exception as error:
                log.debug(error)
                text = cf.box(r.text[:2020], lang='plain')
        else:
            color = discord.Color.red()
            status = f'⛔ {r.status_code}'
            text = cf.box(r.text[:2020], lang='plain')
        embed = discord.Embed(
            title=url,
            url=url,
            color=color,
            description='**Text**\n' + text,
        )
        embed.set_author(name=status)
        embed.add_field(name='Headers', value=cf.box(r.headers))
        await ctx.send(embed=embed)

    @commands.command(name='ipinfo', aliases=['ip', 'ipaddr', 'ipaddress', 'geo'])
    async def ipinfo_command(self, ctx: commands.Context, ip_address: str):
        await ctx.typing()
        try:
            if not re.match(r'^([0-9]{1,3}\.){3}[0-9]{1,3}$', ip_address):
                ip_address, _, _ = socket.gethostbyaddr(ip_address)
            ip = ipaddress.ip_address(ip_address)
            data = await self.get_ip_data(ip.compressed)
            log.debug('data: %s', data)
            description = (
                f"**Country**: {data['country_name']} - {data['country']}/{data['country_code']}\n"
                f"**Region**: {data['region']} - {data['region_code']} / {data['continent_code']}\n"
                f"**City**: {data['city']} / {data['region_code']}\n"
                f"**Lat/Lon**: {data['latitude']} / {data['longitude']}\n"
                f"**Org/ASN**: {data['org']} / {data['asn']}\n"
                f"**Timezone**: {data['timezone']}\n"
            )
            locations = []
            for name, url in self.ip_urls.items():
                if 'WHOIS' in name:
                    continue
                locations.append(f'[{name}]({url.format(ip=ip_address)})')
            description = description.strip() + '\n\n**IP Location Links**\n'
            description += ' | '.join(locations)
            whois = []
            for name, url in self.ip_urls.items():
                if 'WHOIS' not in name:
                    continue
                name = name.replace('WHOIS', '').strip()
                whois.append(f'[{name}]({url.format(ip=ip_address)})')
            description = description.strip() + '\n\n**IP Whois Links**\n'
            description += ' | '.join(whois)
            embed = discord.Embed(
                title=data['ip'],
                description=description,
                color=discord.Color.dark_blue(),
            )
            await ctx.send(embed=embed)

        except Exception as error:
            log.error(error)
            await ctx.send(f'⛔ Error: `{error}`')

    async def get_ip_data(self, ip) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(f'https://ipapi.co/{ip}/json/')
                r.raise_for_status()
            if 'error' in r.json():
                log.debug(r.json())
                return None
            return r.json()
        except Exception as error:
            log.error(error)
            return None
