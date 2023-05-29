import asyncio
import discord
import httpx
import json
import logging
import redis.asyncio as redis
from bs4 import BeautifulSoup
from datetime import timedelta
from typing import Optional, Union, Dict, Any

from redbot.core import commands, app_commands, Config
from redbot.core.bot import Red
from redbot.core.utils import AsyncIter

from .converters import CarlChannelConverter

log = logging.getLogger('red.asn')


class AviationSafetyNetwork(commands.Cog):
    """Carl's Aviation Safety Cog"""

    faa_reg_url = 'https://registry.faa.gov/AircraftInquiry/Search/NNumberResult?nNumberTxt='
    base_url = 'https://aviation-safety.net'
    wiki_n = f'{base_url}/wikibase/dblist.php?Country=N'
    embed_color = 0xF1C40F  # Color for embed
    send_hour_utc = 20  # Auto post at this hour
    sleep_sec = 60*5  # Must be less than 1 hour
    cache_minutes = 10  # Must be less than 1 hour

    chrome_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/113.0.0.0 Safari/537.36')
    http_options = {'follow_redirects': True, 'timeout': 30}
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
        self.loop: Optional[asyncio.Task] = None
        self.client: Optional[redis.Redis] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data = await self.bot.get_shared_api_tokens('redis')
        self.client = redis.Redis(
            host=data['host'] if 'host' in data else 'redis',
            port=int(data['port']) if 'port' in data else 6379,
            db=int(data['db']) if 'db' in data else 0,
            password=data['pass'] if 'pass' in data else None,
        )
        await self.client.ping()
        await self.gen_wiki_data()
        self.loop = asyncio.create_task(self.asn_loop())
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    async def asn_loop(self):
        log.info('%s: Start Main Loop', self.__cog_name__)
        while self is self.bot.get_cog('DayInHistory'):
            log.info(f'Sleeping for {self.sleep_sec} seconds...')
            await asyncio.sleep(self.sleep_sec)
            await self.gen_wiki_data()
            # UPDATE BELOW
            # now = datetime.now()
            # current_time = now.time()
            # if current_time.hour != self.send_hour_utc:
            #     log.debug('%s != %s', current_time.hour, self.send_hour_utc)
            #     continue
            # last = await self.config.last()
            # if last:
            #     last = datetime.fromisoformat(last)
            #     if last.day == now.day:
            #         log.debug('%s == %s', last.day, now.day)
            #         continue
            #
            # log.debug('START')
            # await self.config.last.set(now.isoformat())
            # log.debug('config.last.set(now.isoformat())')
            # all_guilds: dict = await self.config.all_guilds()
            # log.debug('all_guilds: %s', all_guilds)
            # for guild_id, data in await AsyncIter(all_guilds.items()):
            #     log.debug('guild_id: %s', guild_id)
            #     if not data['channel']:
            #         continue
            #     guild: discord.Guild = self.bot.get_guild(guild_id)
            #     channel: discord.TextChannel = guild.get_channel(data['channel'])
            #     data: Dict[str, Any] = await self.get_history(now)
            #     em = discord.Embed.from_dict(data)
            #     await channel.send(embed=em)
            #     log.debug('sleep 5')
            #     await asyncio.sleep(5)
            # log.debug('DONE')

    @commands.hybrid_group(name='asn', aliases=['aviationsafety', 'aviationsafetynetwork'],
                           description='Aviation Safety Network Commands')
    async def _asn(self, ctx: commands.Context):
        """Aviation Safety Network Commands"""

    @_asn.command(name='last', aliases=['l', 'latest'],
                  description="Post the latest entry from Aviation Safety Network")
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.channel)
    async def _asn_post(self, ctx: commands.Context):
        """Post the latest entry from Aviation Safety Network"""
        # TODO: Make this a function
        await ctx.defer()
        data = json.loads(await self.client.get('asn:latest') or '{}')
        if not data:
            await ctx.send('Uhh... No ASN data. Something is wrong...')
            return
        last: dict = data[0]
        log.debug('--- BEGIN last ---')
        log.debug(last)
        log.debug('--- END last ---')
        entry = await self.get_wiki_entry(last)
        embed = await self.gen_embed(entry)
        await ctx.send(embed=embed)

    async def gen_embed(self, data):
        log.debug('--- BEGIN entry/data  ---')
        log.debug(data)
        log.debug('--- END entry/data  ---')

        registration = data['Registration'] if 'Registration' in data else None
        _type = data['Type'] if 'Type' in data else None
        oper = data['Owner/operator'] if 'Owner/operator' in data else None
        img_src = data['img_src'] if 'img_src' in data else None
        location = data['Location'] if 'Location' in data else None
        description = data['Narrative'] if 'Narrative' in data else None
        fatal = data['Fatalities'] if 'Fatalities' in data else 0
        occup = data['Occupants'] if 'Occupants' in data else 0
        phase = data['Phase'] if 'Phase' in data else 0

        em = discord.Embed(
            title=registration or _type or 'Unknown',
            url=f"{self.base_url}{data['href']}",
        )
        if oper:
            url = f"{self.faa_reg_url}{registration}" if registration else None
            em.set_author(name=oper, url=url)
        if img_src:
            em.set_thumbnail(url=f"{self.base_url}{img_src}")

        dlist = []

        if fatal:
            dlist.append(f"\U0001F534 **Fatal/Total:** {fatal} / {occup}")  # 🔴
        else:
            dlist.append(f"**Total Occupants:** {occup}")

        if location:
            dlist.append(f"**Location**: {location}")

        if _type:
            dlist.append(f"**Type**: {_type}")

        if phase:
            dlist.append(f"**Phase**: {phase}")

        dlist.append('')
        dlist.append(description)

        image_url = None
        if data['Sources']:
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
        # join description and return embed
        em.description = '\n'.join(dlist)
        return em

    # @history.command(name='show', aliases=['s'],
    #                  description="Show Today's history, or a specific day, to You Only")
    # @app_commands.describe(date='Date of History to Get, Example: 9-11')
    # async def history_show(self, ctx: commands.Context, *, date: Optional[str]):
    #     """Show Today's history, or a specific day, to You Only"""
    #     # TODO: Make this a function
    #     dt = datetime.now()
    #     if date:
    #         log.debug('date: %s', date)
    #         split = re.split('/|-| ', date)
    #         log.debug('split: %s', split)
    #         str_date = f"{split[0]}-{split[1]}"
    #         log.debug('str_date: %s', str_date)
    #         try:
    #             dt = datetime.strptime(str_date, '%m-%d')
    #         except:
    #             msg = '\U000026D4 Error processing `date`. Example: **9-11**'
    #             await ctx.send(msg, ephemeral=True, delete_after=10)  # ⛔
    #             return
    #     view = HistoryView(self, ctx.author)
    #     await view.send_initial_message(ctx, dt, ephemeral=True)

    # @history.command(name='channel', aliases=['c'],
    #                  description='Admin Only: Set Channel for Auto Posting History Daily')
    # @app_commands.describe(channel='Channel to Post History Too')
    # @commands.max_concurrency(1, commands.BucketType.guild)
    # @commands.guild_only()
    # @commands.admin()
    # async def history_channel(self, ctx: commands.Context, channel: Optional[CarlChannelConverter] = None):
    #     """Admin Only: Set Channel for Auto Posting History Daily"""
    #     channel: discord.TextChannel
    #     log.debug('vt_channel')
    #     if not channel:
    #         await self.config.guild(ctx.guild).channel.set(0)
    #         await ctx.send(f'\U00002705 Disabled. Specify a channel to Enable.', ephemeral=True)  # ✅
    #         return
    #
    #     log.debug('channel: %s', channel)
    #     log.debug('channel.type: %s', channel.type)
    #     if not str(channel.type) == 'text':
    #         await ctx.send('\U000026D4 Channel must be a Text Channel.', ephemeral=True)  # ⛔
    #         return
    #
    #     await self.config.guild(ctx.guild).channel.set(channel.id)
    #     msg = f'\U00002705 Will post daily history in channel: {channel.name}'  # ✅
    #     await ctx.send(msg, ephemeral=True)

    # async def update_data_fuck(self) -> None:
    #     log.debug('update_data')
    #     data = json.loads(await self.client.get('asn:data') or '{}')
    #     await self.client.set('asn:data', json.dumps(data))
    #     return data

    async def get_wiki_entry(self, last: Dict[str, Any]) -> Dict[str, Any]:
        log.debug('asn_wiki_entry')
        # data = json.loads(await self.client.get(f'asn:{href}') or '{}')
        # if data:
        #     log.debug('--- cache call ---')
        #     return data

        log.debug('--- remote call ---')
        url = f"{self.base_url}/{last['href']}"
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, headers=self.http_headers)
        if not r.is_success:
            r.raise_for_status()

        html = r.content.decode('utf-8')
        log.debug('--- BEGIN html  ---')
        log.debug(html)
        log.debug('--- END html  ---')
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table')
        rows = table.find_all('tr')
        data = {'href': last['href']}
        for row in rows:
            caption = row.find('td', class_='caption')
            desc = row.find('td', class_='desc')
            if caption and desc:
                key = caption.get_text(strip=True).rstrip(':')
                value = desc.get_text(strip=True)
                if key == 'Fatalities':
                    fatalities, occupants = value.split('/')
                    fatal = fatalities.split(':')[1].strip() or 0
                    occup = occupants.split(':')[1].strip() or 0
                    data['Fatalities'] = int(fatal)
                    data['Occupants'] = int(occup)
                elif key == 'Type':
                    img_tag = desc.find('img')
                    if img_tag:
                        data['img_src'] = img_tag['src']
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

        # await self.client.setex(
        #     f'asn:{href}',
        #     timedelta(days=self.cache_minutes),
        #     json.dumps(data),
        # )
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
        await self.client.set('asn:latest', json.dumps(entries))


# class HistoryView(discord.ui.View):
#     """Embeds View"""
#     def __init__(self, cog,
#                  author: Union[int, discord.Member, discord.User],
#                  timeout: int = 60*60*2):
#         self.cog: DayInHistory = cog
#         self.user_id: int = author.id if hasattr(author, 'id') else int(author)
#         self.message: Optional[discord.Message] = None
#         self.date: Optional[datetime] = None
#         self.ephemeral: bool = False
#         self.owner_only_sec: int = 120
#         self.created_at = datetime.now()
#         super().__init__(timeout=timeout)
#
#     async def send_initial_message(self, ctx, date, ephemeral: bool = False, **kwargs) -> discord.Message:
#         self.date = date
#         self.ephemeral = ephemeral
#         data = await self.cog.get_history(self.date)
#         embed = discord.Embed.from_dict(data)
#         self.message = await ctx.send(view=self, embed=embed, ephemeral=self.ephemeral, **kwargs)
#         return self.message
#
#     async def interaction_check(self, interaction: discord.Interaction):
#         if interaction.user.id == self.user_id:
#             return True
#         td = datetime.now() - self.created_at
#         if td.seconds >= self.owner_only_sec:
#             return True
#         remaining = self.owner_only_sec - td.seconds
#         msg = (f"\U000026D4 The creator has control for {remaining} more seconds...\n"
#                f"You can create your own response with the `/history` command.")  # ⛔
#         await interaction.response.send_message(msg, ephemeral=True, delete_after=10)
#         return False
#
#     async def on_timeout(self):
#         for child in self.children:
#             child.style = discord.ButtonStyle.gray
#             child.disabled = True
#         await self.message.edit(view=self)
#
#     @discord.ui.button(label='Prev', style=discord.ButtonStyle.green)
#     async def prev_button(self, interaction, button):
#         self.date = self.date - timedelta(days=1)
#         data = await self.cog.get_history(self.date)
#         embed = discord.Embed.from_dict(data)
#         await interaction.response.edit_message(embed=embed)
#
#     @discord.ui.button(label='Next', style=discord.ButtonStyle.green)
#     async def next_button(self, interaction, button):
#         self.date = self.date + timedelta(days=1)
#         data = await self.cog.get_history(self.date)
#         embed = discord.Embed.from_dict(data)
#         await interaction.response.edit_message(embed=embed)
#
#     @discord.ui.button(label='Delete', style=discord.ButtonStyle.red)
#     async def delete_button(self, interaction, button):
#         if not interaction.user.id == self.user_id:
#             msg = ("\U000026D4 Looks like you didn't create this response.\n"
#                    f"You can create your own response with the `/history` command.")  # ⛔
#             await interaction.response.send_message(msg, ephemeral=True, delete_after=10)
#             return
#         await interaction.message.delete()
#         await interaction.response.send_message('\U00002705 Your wish is my command!',
#                                                 ephemeral=True, delete_after=10)  # ✅
