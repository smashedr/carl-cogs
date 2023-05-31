import discord
import httpx
import json
import logging
import re
import redis.asyncio as redis
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any, List

from discord.ext import tasks
from redbot.core import commands, app_commands, Config
from redbot.core.bot import Red

from .converters import CarlChannelConverter

log = logging.getLogger('red.asn')


class AviationSafetyNetwork(commands.Cog):
    """Carl's Aviation Safety Cog"""

    base_url = 'https://aviation-safety.net'
    wiki_n = f'{base_url}/wikibase/dblist.php?Country=N'
    record_url = f'{base_url}/database/record.php?id='
    faa_reg_url = 'https://registry.faa.gov/AircraftInquiry/Search/NNumberResult?nNumberTxt='
    cache_short = 10  # Minutes
    cache_long = 60*2  # Minutes

    http_options = {'follow_redirects': True, 'timeout': 30}
    chrome_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/113.0.0.0 Safari/537.36')
    http_headers = {'user-agent': chrome_agent}

    global_default = {
        'last': None,
    }
    guild_default = {
        'channel': 0,
    }

    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(**self.global_default)
        self.config.register_guild(**self.guild_default)
        self.redis: Optional[redis.Redis] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data = await self.bot.get_shared_api_tokens('redis')
        self.redis = redis.Redis(
            host=data['host'] if 'host' in data else 'redis',
            port=int(data['port']) if 'port' in data else 6379,
            db=int(data['db']) if 'db' in data else 0,
            password=data['pass'] if 'pass' in data else None,
        )
        await self.redis.ping()
        self.main_loop.start()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.main_loop.cancel()

    @tasks.loop(minutes=30.0)
    async def main_loop(self):
        log.info('%s: Run Loop: main_loop', self.__cog_name__)
        await self.gen_wiki_data()

    @commands.hybrid_group(name='asn', aliases=['aviationsafety', 'aviationsafetynetwork'],
                           description='Aviation Safety Network Commands')
    async def _asn(self, ctx: commands.Context):
        """Aviation Safety Network Commands"""

    @_asn.command(name='last', aliases=['l', 'latest'],
                  description="Post the latest entry from Aviation Safety Network")
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.channel)
    async def _asn_last(self, ctx: commands.Context):
        """Post the latest entry from Aviation Safety Network"""
        await ctx.defer()
        data = json.loads(await self.redis.get('asn:latest') or '{}')
        if not data:
            await ctx.send('Uhh... No ASN data. Something is wrong...')
            return

        view = ListView(self, ctx.author, data)
        await view.send_initial_message(ctx, 0)

    @_asn.command(name='post', aliases=['p'],
                  description="Post a specific incident to the current channel")
    @app_commands.describe(entry='Wikibase URL or ID Number')
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.channel)
    async def _asn_post(self, ctx: commands.Context, entry: str):
        """Post a specific incident to the current channel"""
        m = re.search('[0-9-]{4,10}', entry)
        if not m or not m.group(0):
            await ctx.send(f'\U0001F534 Unable to parse ID from entry: {entry}', ephemeral=True, delete_after=10)  # 🔴
            return

        if '-' in m.group(0):
            await ctx.send(f'\U0001F534 Database Entry Records are not currently supported: {entry}', ephemeral=True, delete_after=10)  # 🔴
            return

        await ctx.defer()
        href = f'/wikibase/{m.group(0)}'
        entry = await self.get_wiki_entry(href)
        if not entry:
            await ctx.send(f'\U0001F534 No data for entry: {entry}', ephemeral=True, delete_after=10)  # 🔴
            return
        embed = await self.gen_embed(entry)
        await ctx.send(embed=embed)

    async def gen_embed(self, data):
        log.debug('--- BEGIN entry/data  ---')
        log.debug(data)
        log.debug('--- END entry/data  ---')
        d = data
        dlist = []
        em = discord.Embed(
            title=d['Registration'] or d['Type'] or 'Unknown',
            url=f"{self.base_url}{data['href']}",
            colour=discord.Colour.blue(),
        )
        if d['fatal']:
            em.colour = discord.Colour.red()
        if d['Owner/operator']:
            url = f"{self.faa_reg_url}{d['Registration']}" if d['Registration'] else None
            em.set_author(name=d['Owner/operator'], url=url)
        if d['type_img']:
            em.set_thumbnail(url=f"{self.base_url}{d['type_img']}")
        dlist.append(f"**Fatal/Total/Other:** "
                     f"{d['Fatalities']} / {d['Occupants']} / {d['Other fatalities']}")
        if d['Date']:
            dlist.append(f"**Date**: {d['Date']}")
        if d['Time']:
            dlist.append(f"**Time**: {d['Time']}")
        if d['Location']:
            dlist.append(f"**Location**: {d['Location']}")
        if d['Phase']:
            dlist.append(f"**Phase**: {d['Phase']}")
        if d['Type']:
            dlist.append(f"**Type**: {d['Type']}")

        dlist.append('')
        dlist.append(data['Narrative'])

        image_url = None
        if 'Sources' in data and data['Sources']:
            for s in data['Sources']:
                st = s.replace('http://', '').replace('https://', '')[:50]
                dlist.append(f"[{st}..]({s})")
                images = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
                if s.lower().endswith(images):
                    image_url = s
                    break
        log.debug('image_url: %s', image_url)
        if image_url:
            em.set_image(url=image_url)

        if data['datetime']:
            dt = datetime.fromisoformat(data['datetime'])
            em.timestamp = dt

        em.description = '\n'.join(dlist)
        return em

    async def get_wiki_entry(self, href: str) -> Dict[str, Any]:
        log.debug('get_wiki_entry')
        log.debug('href: %s', href)

        data = json.loads(await self.redis.get(f'asn:{href}') or '{}')
        if data:
            log.debug('--- cache call ---')
            return data

        log.debug('--- remote call ---')
        url = f"{self.base_url}/{href}"
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, headers=self.http_headers)
        if not r.is_success:
            r.raise_for_status()

        html = r.content.decode('utf-8')
        # log.debug('--- BEGIN html  ---')
        # log.debug(html)
        # log.debug('--- END html  ---')
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table')
        rows = table.find_all('tr')
        data = {}
        for row in rows:
            cells = row.find_all('td')
            caption = cells[0]
            desc = cells[1]
            # caption = row.find('td', class_='caption')
            # desc = row.find('td', class_='desc')
            if caption:
                key = caption.get_text(strip=True).rstrip(':')
                value = desc.get_text(strip=True) if desc else None
                if key == 'Fatalities':
                    fatalities, occupants = value.split('/')
                    fatal = fatalities.split(':')[1].strip() or '0'
                    occup = occupants.split(':')[1].strip() or '0'
                    data['Fatalities'] = int(fatal) if fatal.isdigit() else None
                    data['Occupants'] = int(occup) if occup.isdigit() else None
                elif key == 'Other fatalities':
                    other = value.strip() or '0'
                    data['Other fatalities'] = int(other) if other.isdigit() else None
                elif key == 'Type':
                    type_img = desc.find('img')
                    data['type_img'] = type_img if type_img else None
                    if type_img:
                        data['type_img'] = type_img['src']
                    data[key] = value
                elif key == 'Location':
                    data[key] = value.replace('United States of America', '').strip('- ')
                else:
                    data[key] = value

        narrative = soup.find('span', class_='caption', string='Narrative:')
        if narrative:
            data['Narrative'] = narrative.find_next_sibling('span').get_text() + '\n'

        sources_div = soup.find('div', class_='captionhr', string='Sources:')
        if sources_div:
            sources = sources_div.find_next_siblings('a')
            data['Sources'] = [source['href'] for source in sources]

        req = ['Date', 'Time', 'Type', 'Owner/operator', 'Registration', 'MSN', 'Fatalities', 'Occupants',
               'Other fatalities', 'Aircraft damage', 'Category', 'Location', 'Phase', 'Nature', 'Departure airport',
               'Destination airport', 'Investigating agency', 'Confidence Rating', 'Narrative', 'Sources']
        for x in req:
            if x not in data:
                log.debug('%s - Missing: %s', href, x)
                data[x] = None

        data['fatal'] = data['Fatalities'] or data['Other fatalities']
        data['href'] = href

        if data['Date'] and data['Time']:
            m = re.search('[0-9]{2}:[0-9]{2}', data['Time'])
            time = m.group(0) if (m and m.group(0)) else '00:00'
            _str = f"{data['Date']} {m.group(0)}"
            _fmt = '%d-%b-%Y %H:%M'
        elif data['Date']:
            _str = f"{data['Date']}"
            _fmt = '%d-%b-%Y'
        data['datetime'] = None
        cache_min = self.cache_short
        if data['Date']:
            try:
                dt = datetime.strptime(_str, _fmt)
                data['datetime'] = dt.isoformat()
                diff = datetime.now() - dt
                if diff.days >= 1:
                    cache_min = self.cache_long
            except Exception as error:
                log.exception(error)
                pass

        await self.redis.setex(
            f"asn:{data['href']}",
            timedelta(minutes=cache_min),
            json.dumps(data),
        )
        return data

    async def gen_wiki_data(self) -> None:
        log.debug('gen_wiki_data')
        log.debug('--- remote call ---')
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(self.wiki_n, headers=self.http_headers)
        if not r.is_success:
            r.raise_for_status()
        html = r.content.decode('utf-8')
        # log.debug('--- BEGIN html  ---')
        # log.debug(html)
        # log.debug('--- END html  ---')
        soup = BeautifulSoup(html, 'html.parser')
        table_rows = soup.find_all('tr', class_=['list', 'listmain'])
        entries = []

        for row in table_rows:
            row_data = {}
            cells = row.find_all('td', class_=['list', 'listmain'])
            headers = ['date', 'type', 'registration', 'operator', 'fatal', 'location', 'flag', 'dmg', 'r', 'e']
            for i, cell in enumerate(cells):
                header = headers[i]
                if header in ['e', 'r']:
                    continue
                if header in ['date']:
                    row_data[header] = cell.text.strip()
                    link = cell.find('a')
                    if link:
                        row_data['href'] = link['href']
                if header in ['flag']:
                    img = cell.find('img')
                    row_data[header] = img['src'] if img else None
                else:
                    row_data[header] = cell.text.strip()
            entries.append(row_data)

        # log.debug('--- BEGIN entries  ---')
        # log.debug(entries)
        # log.debug('--- END entries  ---')
        await self.redis.set('asn:latest', json.dumps(entries))


class ListView(discord.ui.View):
    """Embeds View"""
    def __init__(self, cog,
                 author: Union[int, discord.Member, discord.User], data_list: List[dict],
                 timeout: int = 60*60*2):
        self.cog: AviationSafetyNetwork = cog
        self.user_id: int = author.id if hasattr(author, 'id') else int(author)
        self.data_list: List[dict] = data_list
        self.message: Optional[discord.Message] = None
        self.index: int = 0
        self.ephemeral: bool = False
        self.owner_only_sec: int = 120
        self.created_at = datetime.now()
        super().__init__(timeout=timeout)

    async def send_initial_message(self, ctx, index: int = 0, ephemeral: bool = False, **kwargs) -> discord.Message:
        self.index = index
        self.ephemeral = ephemeral
        accidents = self.data_list[self.index]
        entry = await self.cog.get_wiki_entry(accidents['href'])
        embed = await self.cog.gen_embed(entry)
        self.message = await ctx.send(view=self, embed=embed, ephemeral=self.ephemeral, **kwargs)
        return self.message

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.user_id:
            return True
        td = datetime.now() - self.created_at
        if td.seconds >= self.owner_only_sec:
            return True
        remaining = self.owner_only_sec - td.seconds
        msg = (f"\U000026D4 The creator has control for {remaining} more seconds...\n"
               f"You can create your own response with the `/asn` command.")  # ⛔
        await interaction.response.send_message(msg, ephemeral=True, delete_after=10)
        return False

    async def on_timeout(self):
        for child in self.children:
            child.style = discord.ButtonStyle.gray
            child.disabled = True
        self.stop()
        await self.message.edit(view=self)

    @discord.ui.button(label='Prev', style=discord.ButtonStyle.green)
    async def prev_button(self, interaction: discord.Interaction, button):
        if not self.index < len(self.data_list) - 1:
            log.debug('end of list: %s', self.index)
            msg = 'At the end, use: `Next`'
            await interaction.response.send_message(msg, ephemeral=True, delete_after=4)
            return

        await interaction.response.defer()
        log.debug('prev.index.before: %s', self.index)
        self.index = self.index + 1
        log.debug('prev.index.after: %s', self.index)
        accidents = self.data_list[self.index]
        entry = await self.cog.get_wiki_entry(accidents['href'])
        embed = await self.cog.gen_embed(entry)
        await self.message.edit(embed=embed)

    @discord.ui.button(label='Next', style=discord.ButtonStyle.green)
    async def next_button(self, interaction: discord.Interaction, button):
        if self.index < 1:
            log.debug('beginning of list: %s', self.index)
            msg = 'At the beginning, use: `Prev`'
            await interaction.response.send_message(msg, ephemeral=True, delete_after=4)
            return

        await interaction.response.defer()
        log.debug('next.index.before: %s', self.index)
        self.index = self.index - 1
        log.debug('next.index.after: %s', self.index)
        accidents = self.data_list[self.index]
        entry = await self.cog.get_wiki_entry(accidents['href'])
        embed = await self.cog.gen_embed(entry)
        await self.message.edit(embed=embed)

    @discord.ui.button(label='Delete', style=discord.ButtonStyle.red)
    async def delete_button(self, interaction: discord.Interaction, button):
        if not interaction.user.id == self.user_id:
            msg = ("\U000026D4 Looks like you didn't create this response.\n"
                   f"You can create your own response with the `/history` command.")  # ⛔
            await interaction.response.send_message(msg, ephemeral=True, delete_after=10)
            return
        self.stop()
        await interaction.message.delete()
        await interaction.response.send_message('\U00002705 Your wish is my command!',
                                                ephemeral=True, delete_after=10)  # ✅