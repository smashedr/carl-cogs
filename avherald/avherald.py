import discord
import html2text
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
from redbot.core.utils import AsyncIter

log = logging.getLogger('red.avherald')


class Avherald(commands.Cog):
    """Carl's Avherald Cog"""

    base_url = 'https://avherald.com'
    http_options = {'follow_redirects': True, 'timeout': 30}
    chrome_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/113.0.0.0 Safari/537.36')
    http_headers = {'user-agent': chrome_agent}

    global_default = {
        'last': [],
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

    @tasks.loop(minutes=60.0)
    async def main_loop(self):
        await self.bot.wait_until_ready()
        log.info('%s: Start Loop: main_loop', self.__cog_name__)
        try:
            await self.gen_wiki_data()
        except Exception as error:
            return log.error('Error Generating Wiki Data: %s', error)
        data: List[dict] = json.loads(await self.redis.get('avherald:latest') or '[]')
        if not data:
            return log.error('No AVHerald Data.')
        last: List[str] = await self.config.last()
        if not last:
            log.warning('First Run Detected! No last found, setting now.')
            newlast = [x['id'] for x in data]
            log.debug('newlast: %s', newlast)
            await self.config.last.set(newlast)
            return
        for d in reversed(data):
            if d['id'] not in last:
                log.info('%s not in last, sending notification.', d['id'])
                await self.process_post_entry(d)
                last.insert(0, d['id'])
        await self.config.last.set(last[:200])
        log.info('%s: Finish Loop: main_loop', self.__cog_name__)

    async def process_post_entry(self, entry: Dict[str, Any]):
        log.debug('Start Entry ID: %s', entry['id'])
        wiki_data = await self.get_wiki_entry(entry)
        embed = await self.gen_embed(wiki_data)
        all_guilds: dict = await self.config.all_guilds()
        for guild_id, data in await AsyncIter(all_guilds.items(), delay=10, steps=5):
            if not data['channel']:
                log.debug('disabled: guild_id: %s', guild_id)
                continue
            log.debug('enabled: guild_id: %s', guild_id)
            guild: discord.Guild = self.bot.get_guild(guild_id)
            channel: discord.TextChannel = guild.get_channel(data['channel'])
            await channel.send(embed=embed)
        log.debug('Finish Entry ID: %s', entry['id'])

    @commands.hybrid_group(name='avherald', aliases=['avh'], description='AVHerald Commands')
    async def _avherald(self, ctx: commands.Context):
        """AVHerald Commands"""

    @_avherald.command(name='last', aliases=['l'],
                  description="Post the latest entry from Aviation Safety Network")
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.channel)
    async def _avherald_last(self, ctx: commands.Context):
        """Post the latest entry from Aviation Safety Network"""
        await ctx.defer()
        data = json.loads(await self.redis.get('avherald:latest') or '{}')
        if not data:
            await ctx.send('Uhh... No AVHerald data. Something is wrong...')
            return

        view = ListView(self, ctx.author, data)
        await view.send_initial_message(ctx, 0)

    # @_avherald.command(name='show', aliases=['s'],
    #               description="Show the latest entry from Aviation Safety Network to You Only")
    # @commands.cooldown(rate=1, per=15, type=commands.BucketType.channel)
    # async def _avherald_last(self, ctx: commands.Context):
    #     """Show the latest entry from Aviation Safety Network to You Only"""
    #     await ctx.defer(ephemeral=True)
    #     data = json.loads(await self.redis.get('avherald:latest') or '{}')
    #     if not data:
    #         await ctx.send('Uhh... No AVHerald data. Something is wrong...')
    #         return
    #
    #     view = ListView(self, ctx.author, data)
    #     await view.send_initial_message(ctx, 0, True)

    # @_avherald.command(name='post', aliases=['p'],
    #               description="Post a specific incident to the current channel")
    # @app_commands.describe(entry='Wikibase URL or ID Number')
    # @commands.cooldown(rate=1, per=15, type=commands.BucketType.channel)
    # async def _avherald_post(self, ctx: commands.Context, entry: str):
    #     """Post a specific incident to the current channel"""
    #     m = re.search('[0-9-]{4,10}', entry)
    #     if not m or not m.group(0):
    #         await ctx.send(f'\U0001F534 Unable to parse ID from entry: {entry}', ephemeral=True, delete_after=10)  # 🔴
    #         return
    #
    #     if '-' in m.group(0):
    #         await ctx.send(f'\U0001F534 Database Entry Records are not currently supported: {entry}', ephemeral=True, delete_after=10)  # 🔴
    #         return
    #
    #     await ctx.defer()
    #     href = f'/wikibase/{m.group(0)}'
    #     entry = await self.get_wiki_entry(href)
    #     if not entry:
    #         await ctx.send(f'\U0001F534 No data for entry: {entry}', ephemeral=True, delete_after=10)  # 🔴
    #         return
    #     embed = await self.gen_embed(entry)
    #     await ctx.send(embed=embed)

    @_avherald.command(name='channel', aliases=['c'],
                       description='Set Channel for Auto Posting Aviation Herald Entries')
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.guild_only()
    @commands.admin()
    async def _avherald_channel(self, ctx: commands.Context):
        """Set Channel for Auto Posting Aviation Herald Entries"""
        view = ChannelView(self, ctx.author)
        msg = 'Select a channel to Auto Post **Avation Herald** Updates:'
        await view.send_initial_message(ctx, msg, True)

    async def gen_embed(self, data):
        log.debug('--- BEGIN entry/data  ---')
        log.debug(data)
        log.debug('--- END entry/data  ---')
        d = data
        cdict = {
            'Incident': discord.Colour.yellow(),
            'Accident': discord.Colour.orange(),
            'Crash': discord.Colour.red(),
            'News': discord.Colour.green(),
            'Report': discord.Colour.blue(),
        }
        embed = discord.Embed(
            title=data['op_type'],
            url=f"{self.base_url}{data['href']}",
            colour=cdict[data['incident']],
        )
        embed.set_author(name=data['issue'])

        dlist = []
        if d['incident']:
            dlist.append(f"**Incident**: {d['incident']}")
        if d['issue']:
            dlist.append(f"**Issue**: {d['issue']}")
        if d['location']:
            dlist.append(f"**Location**: {d['location']}")
        if d['date']:
            dlist.append(f"**Date**: {d['date']}")
        if d['posted']:
            dlist.append(f"**Updated**: {d['posted']}")

        dlist.append(f"\n**{data['title']}:**\n")
        text = data['text'][:2800] + '...\n' if len(data['text']) > 3400 else data['text']
        dlist.append(text)

        if data['links']:
            for link in data['links']:
                text = link.replace('http://', '').replace('https://', '')[:50]
                dlist.append(f"[{text}..]({link})")

        if data['images']:
            embed.set_image(url=data['images'][0])

        # if data['date']:
        #     try:
        #         date_string = data['date'].replace('st', '').replace('nd', '').replace('rd', '').replace('th', '')
        #         # date_object = datetime.strptime(date_string, '%B %d %Y')
        #         log.debug('date_string: %s', date_string)
        #         date_object = datetime.strptime(date_string, '%b %d %Y')
        #         embed.timestamp = date_object
        #     except Exception as error:
        #         log.exception(error)

        embed.description = '\n'.join(dlist)
        return embed

    async def get_wiki_entry(self, entry: dict) -> Dict[str, Any]:
        log.debug('get_wiki_entry: data: %s', entry)
        data = json.loads(await self.redis.get(f'avherald:{entry["href"]}') or '{}')
        if data:
            log.debug('--- cache call ---')
            return data

        log.debug('--- remote call ---')
        url = f'{self.base_url}{entry["href"]}'
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, headers=self.http_headers)
            r.raise_for_status()

        html = r.text
        soup = BeautifulSoup(html, 'html.parser')
        div_element = soup.find('div', attrs={'align': 'left'})
        sitetext_span = div_element.find('span', class_='sitetext')
        anchor_tags = sitetext_span.find_all('a')
        links = [anchor_tag.get('href') for anchor_tag in anchor_tags]
        for anchor_tag in anchor_tags:
            anchor_tag.extract()
        img_tags = sitetext_span.find_all('img')
        images = [img_tag.get('src') for img_tag in img_tags]

        log.debug('-'*40)
        h = html2text.HTML2Text()
        h.body_width = 0
        text = h.handle(str(sitetext_span))
        text = text.strip()
        log.debug(text)
        log.debug('-'*40)
        data = {'text': text, 'links': links, 'images': images}
        data.update(entry)
        await self.redis.setex(
            f'avherald:{data["href"]}',
            timedelta(hours=2),
            json.dumps(data),
        )
        return data

    async def gen_wiki_data(self) -> None:
        log.debug('gen_wiki_data')
        log.debug('--- remote call ---')
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(self.base_url, headers=self.http_headers)
            r.raise_for_status()
        html = r.text
        soup = BeautifulSoup(html, 'html.parser')
        rows = soup.find('td', id='ad1cell', class_='center_td').find_all('tr')
        entries = []
        current_date = ''
        for row in rows:
            date_span = row.find('span', class_='bheadline_avherald')
            if date_span:
                current_date = date_span.text.strip()
            incident_data = row.find('img', class_='frame')
            if incident_data:
                incident_type: str = incident_data['alt']
                incident_href: str = row.find('a')['href']
                incident_title: str = row.find('span', class_='headline_avherald').text.strip()

                split = incident_title.split(' on ')
                op_type_loc = split[0].strip()
                split.pop(0)
                date_issue = ' on '.join(split).strip()

                split = date_issue.split(', ')
                date = split[0].strip()
                split.pop(0)
                issue = ', '.join(split).strip()

                op_type, location = None, None
                for term in [' enroute ', ' over ', ' near ', ' at ']:
                    if term in op_type_loc:
                        split = op_type_loc.split(term)
                        op_type = split[0].strip()
                        split.pop(0)
                        location = term.join(split).strip()
                match = re.search(r'article=(\w+)', incident_href)
                if not match or not match.group(1):
                    log.debug('ARTICLE NO ID: %s', incident_href)
                    continue
                entry = {
                    'id': match.group(1),
                    'posted': current_date,
                    'incident': incident_type,
                    'href': incident_href,
                    'title': incident_title,
                    'date': date,
                    'issue': issue,
                    'location': location,
                    'op_type': op_type,
                }
                if entry not in entries:
                    entries.append(entry)
        await self.redis.set('avherald:latest', json.dumps(entries))


class ListView(discord.ui.View):
    """Embeds View"""
    def __init__(self, cog,
                 author: Union[int, discord.Member, discord.User], data_list: List[dict],
                 timeout: int = 60*60*2):
        self.cog = cog
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
        log.debug('ephemeral: %s', ephemeral)
        self.ephemeral = ephemeral
        log.debug('self.ephemeral: %s', self.ephemeral)
        accidents = self.data_list[self.index]
        entry = await self.cog.get_wiki_entry(accidents)
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
               f"You can create your own response with the `/avherald` command.")  # ⛔
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
        entry = await self.cog.get_wiki_entry(accidents)
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
        entry = await self.cog.get_wiki_entry(accidents)
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


class ChannelView(discord.ui.View):
    def __init__(self, cog, author: Union[discord.Member, discord.User, int],
                 timeout: int = 60 * 3):
        self.cog = cog
        self.user_id: int = author.id if hasattr(author, 'id') else int(author)
        self.ephemeral: bool = False
        self.message: Optional[discord.Message] = None
        super().__init__(timeout=timeout)

    async def send_initial_message(self, ctx, message: Optional[str] = None,
                                   ephemeral: bool = False, **kwargs) -> discord.Message:
        self.ephemeral = ephemeral
        self.message = await ctx.send(content=message, view=self, ephemeral=self.ephemeral, **kwargs)
        return self.message

    async def on_timeout(self):
        await self.message.delete()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.user_id:
            return True
        msg = f"\U000026D4 Looks like you did not create this response."  # ⛔
        await interaction.response.send_message(msg, ephemeral=True, delete_after=60)
        return False

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text],
                       min_values=0, max_values=1)
    async def select_channels(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        response = interaction.response
        channels: List = []
        for value in select.values:
            channels.append(value)
        if not channels:
            await self.cog.config.guild(interaction.guild).channel.set(0)
            msg = f'No Channel Selected. Auto Posts Disabled.'
            return await response.send_message(msg, ephemeral=True, delete_after=60)
        await self.cog.config.guild(interaction.guild).channel.set(channels[0].id)
        msg = f'Now Auto Posting to Channel {channels[0].mention}'
        return await response.send_message(msg, ephemeral=True, delete_after=60)
