import base64
import discord
import httpx
import json
import logging
import re
import io

import redis.asyncio as redis
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from html import unescape
from typing import Optional, List, Tuple, Dict, Union

from redbot.core import commands, app_commands
from redbot.core.bot import Red
from redbot.core.utils import chat_formatting as cf

from .fa import FlightAware

log = logging.getLogger('red.captcha')


class Flightaware(commands.Cog):
    """Carl's FlightAware Cog"""

    def __init__(self, bot):
        self.bot: Red = bot
        self.api_key: Optional[str] = None
        self.client: Optional[redis.Redis] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data = await self.bot.get_shared_api_tokens('flightaware')
        self.api_key = data['api_key']
        data = await self.bot.get_shared_api_tokens('redis')
        self.client = redis.Redis(
            host=data['host'] if 'host' in data else 'redis',
            port=int(data['port']) if 'port' in data else 6379,
            db=int(data['db']) if 'db' in data else 0,
            password=data['pass'] if 'pass' in data else None,
        )
        await self.client.ping()
        await self.gen_wiki_type_data()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.content:
            return
        if 3 > len(message.content) > 7:
            return
        split = message.content.split()
        if len(split) > 1:
            return
        m = re.search('[a-zA-Z0-9]{2,3}[0-9]{1,4}', split[0].upper())
        if not m or not m.group(0):
            return

        fn = m.group(0).upper()
        log.debug('FN: %s', fn)
        m = re.search('[a-zA-Z]{3}[0-9]{1,4}', fn)
        if not m or not m.group(0):
            return

        valid = False
        file = '/data/cogs/flightaware/icao.txt'
        with open(file) as f:
            if fn[:3] in f.read():
                valid = True
                log.debug('ICAO')
        if not valid:
            file = '/data/cogs/flightaware/iata.txt'
            with open(file) as f:
                if fn[:2] in f.read():
                    valid = True
                    log.debug('IATA')
        if not valid:
            log.debug('NONE')
            log.warning('FN Regex Match but NO Airline Code Match')
            return

        log.debug('SUCCESS: matched fn to ac')
        await self.process_flight(message.channel, message.author, fn, silent=True)

        # m = re.search('[a-zA-Z]{2,3}', fn)
        # if not m or not m.group(0):
        #     log.error('Matched word but not FN')
        #     return
        # ac = m.group(0)
        # log.debug(ac)
        # if len(ac) == 2:
        #     file = '/data/cogs/flightaware/iata.txt'
        # else:
        #     file = '/data/cogs/flightaware/icao.txt'
        # with open(file) as f:
        #     if ac not in f.read():
        #         return

    @commands.hybrid_command(name='flight', aliases=['f'], description='Get Flight Information')
    async def flight(self, ctx: commands.Context, ident: str):
        """Get Flight Information for: <ident>"""
        await self.process_flight(ctx, ctx.author, ident)

    @commands.hybrid_group(name='fa', aliases=['flightaware'], description='FlightAware Commands')
    @commands.guild_only()
    async def fa(self, ctx: commands.Context):
        """FlightAware Commands."""

    @fa.command(name='flight', description='Get Flight Information')
    @app_commands.describe(ident='Flight Number or Registration Number')
    async def fa_flight(self, ctx: commands.Context, ident: str):
        """Get Flight Information for: <ident>"""
        await self.process_flight(ctx, ctx.author, ident)

    async def process_flight(self, ctx, author, ident_str: str, silent=False):
        ctx: commands.Context
        author: Union[discord.Member, discord.User]
        ident: str = self.validate_ident(ident_str)
        if not ident:
            if silent:
                return
            await ctx.send(F'Unable to validate `ident`: **{ident_str}**', ephemeral=True, delete_after=10)
            return
        fa = FlightAware(self.api_key)
        fdata = json.loads(await self.client.get(f'fa:{ident}') or '{}')
        if not fdata:
            log.info('--- API CALL ---')
            fdata = await fa.flights_ident(ident)
            log.debug(fdata)
            await self.client.setex(
                f'fa:{ident}',
                timedelta(minutes=5),
                json.dumps(fdata or {}),
            )
        if 'flights' not in fdata or not fdata['flights']:
            if silent:
                return
            msg = f'No flights found for ident: **{ident}**\n'
            await ctx.send(msg, ephemeral=True, delete_after=10)
            return

        # total = len(fdata['flights'])
        # log.debug('total: %s', total)
        # live, past, sched = [], [], []
        # for d in fdata['flights']:
        #     if int(d['progress_percent']) == 0:
        #         sched.append(d)
        #     elif int(d['progress_percent']) == 100:
        #         past.append(d)
        #     else:
        #         live.append(d)
        # log.debug('-'*20)
        # log.debug('live: %s', len(live))
        # log.debug('past: %s', len(past))
        # log.debug('sched: %s', len(sched))
        # msgs = [f'**{ident}**: Live: `{len(live)}`  Sched: `{len(sched)}`  Past: `{len(past)}`']
        # if len(live) > 1 and len(sched) == 0:
        #     await ctx.send(' '.join(msgs))
        #     return

        embeds = []
        index = 0
        content = f'Flights for **{ident}**'
        for i, d in enumerate(reversed(fdata['flights'])):
            em = discord.Embed(
                title=d['fa_flight_id'],
                colour=discord.Colour.light_gray(),
            )
            if d['status'] and 'scheduled' in d['status'].lower():
                em.colour = discord.Colour.blue()
            off = d['actual_off'] or d['estimated_off'] or d['scheduled_off']
            off_dt = datetime.strptime(off, '%Y-%m-%dT%H:%M:%SZ')
            if off_dt:
                em.timestamp = off_dt
                if not index:
                    if datetime.now() > off_dt:
                        index = i
            oper_icao = d['operator_icao'] or d['operator'] or d['operator_iata']
            msgs = []
            matches = ['on the way', 'en route']
            if (d['progress_percent'] and (0 < d['progress_percent'] < 100)) \
                    or any([x in d['status'].lower() for x in matches]):
                index = i
                msgs.append(f'\U0001F7E2 [Live Now on FlightAware]({fa.fa_flight_url}{ident}) ')  # :green_circle:
                em.colour = discord.Colour.green()
            if d['position_only']:
                msgs.append(f'\U0001F535 **Position Only!** ')  # 🔵
            if d['cancelled']:
                msgs.append(f'\U0001F534 **Cancelled!** ')  # 🔴
            if d['diverted']:
                msgs.append(f'\U0001F7E1 **Diverted!** ')  # :yellow_circle:
            msgs = ['\n'.join(msgs)]
            msgs.append(
                f"```ini\n"
                f"[Operator]:   {d['operator_icao']} / {d['operator_iata']}\n"
                f"[ICAO/IATA]:  {d['ident_icao']} / {d['ident_iata']}\n"
                f"[Status]:     {d['status']}\n"
                f"[Distance]:   {d['route_distance']} nm / {d['progress_percent']}%\n"
                f"[Aircraft]:   {d['aircraft_type']} / {d['registration']}"
            )
            if d['origin'] and d['destination']:
                msgs.append(
                    f"\n[Takeoff]:    {d['actual_off']}\n"
                    f"[From]:       {d['origin']['code']} / {d['origin']['name']}\n"
                    f"[ETA]:        {d['estimated_on']}\n"
                    f"[To]:         {d['destination']['code']} / {d['destination']['name']}"
                )
            if d['gate_destination'] and d['baggage_claim']:
                msgs.append(f"\n[Gate/Bags]:  {d['gate_destination']} / {d['baggage_claim']}")
            elif d['gate_destination']:
                msgs.append(f"\n[Gate]:       {d['gate_destination']}")
            elif d['route']:
                msgs.append(f"\n[Route]:      {d['route']}")
            if d['codeshares']:
                msgs.append(f"\n[Codeshares]: {cf.humanize_list(d['codeshares'])}")
            msgs.append(f"```")
            value = ''
            if d['registration']:
                value += f"[{d['registration']}]({fa.fa_registration_url}{d['registration']}) " \
                         f"[\U0001F5BC\U0000FE0F]({fa.jetphotos_url}{d['registration']}) | "  # 🖼️
            if d['aircraft_type']:
                wiki_url = await self.get_wiki_url(d['aircraft_type'])
                if wiki_url:
                    value += f"[{d['aircraft_type']}]({wiki_url}) | "
                else:
                    value += f"{d['aircraft_type']} | "
            if d['origin'] and d['origin']['code_icao']:
                value += f"[{d['origin']['code_icao']}]({fa.airnav_url}{d['origin']['code_icao']}) " \
                         f"[\U0001F508]({fa.liveatc_url}{d['origin']['code_icao']}) | "  # 🔈
            if d['destination'] and d['destination']['code_icao']:
                value += f"[{d['destination']['code_icao']}]({fa.airnav_url}{d['destination']['code_icao']}) " \
                         f"[\U0001F508]({fa.liveatc_url}{d['destination']['code_icao']}) | "  # 🔈
            value = value.strip('| ')
            # value += f"\n{i+1}/{len(fdata['flights'])}"
            em.add_field(name='Links', value=value)
            em.set_footer(text=f"{i+1}/{len(fdata['flights'])}")
            # msgs.append(f"{i+1}/{len(fdata['flights'])}")
            em.description = ' '.join(msgs)
            embeds.append(em)
        log.debug('embeds: %s', len(embeds))
        log.debug('index: %s', index)
        view = EmbedsView(self, embeds, oper_icao, index=index)
        await view.send_initial_message(ctx, author, content=content)

    @fa.command(name='operator', description='Airline Operator Information')
    @app_commands.describe(code='Airline ICAO or IATA Identifier')
    async def fa_operator(self, ctx: commands.Context, code: str):
        """Get Airline Operator info for: <id>"""
        log.debug('code: %s', code)
        operator_id = self.validate_ident(code)
        log.debug('operator_id: %s', operator_id)
        if not operator_id:
            await ctx.send(F'Unable to validate `id`: **{code}**', ephemeral=True, delete_after=10)
            return

        fa = FlightAware(self.api_key)
        fdata = json.loads(await self.client.get(f'fa:{operator_id}') or '{}')
        log.debug(fdata)
        if not fdata:
            log.info('--- API CALL ---')
            fdata = await fa.operators_id(operator_id)
            log.debug(fdata)
        if not fdata:
            await ctx.send(f'No results for operator id: `{operator_id}`', ephemeral=True, delete_after=10)
            return

        await self.client.setex(f'fa:{operator_id}', timedelta(days=30), json.dumps(fdata))
        d = fdata
        msgs = [(
            f"Operator: **{d['name']}** "
            f"```ini\n"
            f"[ICAO/IATA]:  {d['icao']} / {d['iata']}\n"
            f"[Callsign]:   {d['callsign']}\n"
            f"[Short]:      {d['shortname']}\n"
            f"[Country]:    {d['country']}"
        )]
        if d['location']:
            msgs.append(f"\n[Location]:   {d['location']}")
        if d['phone']:
            msgs.append(f"\n[Phone]:      {d['phone']}")
        msgs.append(f"```")
        buttons = {}
        if d['url']:
            buttons.update({'Website': d['url']})
        if d['wiki_url']:
            buttons.update({'Wikipedia': d['wiki_url']})
        await ctx.send(' '.join(msgs), view=ButtonsURLView(buttons))

    @fa.command(name='registration', description='Aircraft Registration Information')
    @app_commands.describe(ident='Aircraft Registration or Flight Number')
    async def fa_registration(self, ctx: commands.Context, ident: str):
        """Get Aircraft Registration info for: <ident>"""
        log.debug('ident: %s', ident)
        identifier = self.validate_ident(ident)
        log.debug('identifier: %s', identifier)
        if not identifier:
            await ctx.send(F'Unable to validate `id`: **{ident}**', ephemeral=True, delete_after=10)
            return

        fa = FlightAware(self.api_key)
        fdata = json.loads(await self.client.get(f'fa:{identifier}') or '{}')
        log.debug(fdata)
        if not fdata:
            log.info('--- API CALL ---')
            fdata = await fa.owner_ident(identifier)
            log.debug(fdata)
        if not fdata:
            await ctx.send(f'No results for ident: `{identifier}`', ephemeral=True, delete_after=10)
            return

        await self.client.setex(f'fa:{identifier}', timedelta(days=30), json.dumps(fdata))
        d = fdata['owner']
        msg = (
            f"Registration: **{identifier}** "
            f"```ini\n"
            f"[Name]:         {d['name']}\n"
            f"[Location]:     {d['location']}\n"
            f"[Location]:     {d['location2']}"
            f"```"
        )
        buttons = {
            'FA': f'{fa.fa_registration_url}{identifier}',
            'Photos': f'{fa.jetphotos_url}{identifier}',
            'AirFleets': f'{fa.airfleets_search_url}{identifier}',
        }
        if d['website']:
            buttons.update({'Website': d['website']})
        view = ButtonsURLView(buttons)
        await ctx.send(unescape(msg), view=view)

    async def get_wiki_url(self, icao_type: str) -> Optional[str]:
        icao_type = icao_type.upper()
        base_url = f'https://en.wikipedia.org'
        try:
            aircraft_data = json.loads(await self.client.get('fa:wiki_aircraft_type') or '{}')
            if not aircraft_data:
                aircraft_data = await self.gen_wiki_type_data()
            if aircraft_data:
                if icao_type in aircraft_data:
                    return f'{base_url}{aircraft_data[icao_type]}'
        except Exception as error:
            log.exception(error)

    async def gen_wiki_type_data(self) -> dict:
        # TODO: Make this a task in a loop
        log.info('--- REMOTE CALL ---')
        url = f'https://en.wikipedia.org/wiki/List_of_aircraft_type_designators'
        http_options = {
            'follow_redirects': True,
            'timeout': 30,
        }
        async with httpx.AsyncClient(**http_options) as client:
            r = await client.get(url)
        if not r.is_success:
            r.raise_for_status()
        html = r.content.decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        rows = soup.find('table').find('tbody').find_all('tr')
        aircraft_data = {}
        for row in rows:
            columns = row.find_all('td')
            if not columns:
                continue
            icao_type = columns[0].text.strip()
            model_href = columns[2].find('a')['href']
            aircraft_data[icao_type] = model_href
        log.debug('-'*20)
        log.debug(aircraft_data)
        await self.client.setex(
            'fa:wiki_aircraft_type',
            timedelta(days=7),
            json.dumps(aircraft_data),
        )
        return aircraft_data

    @staticmethod
    def validate_ident(ident: str) -> Optional[str]:
        # m = re.search('[a-zA-Z0-9]{2,3}[0-9]{1,4}', ident.upper())
        m = re.search('[a-zA-Z0-9-]{2,7}', ident.upper())
        if m and m.group(0):
            return m.group(0)

    # async def process_live_flight(self, ctx, ident: str):
    #     fa = FlightAware(self.api_key')
    #     fdata = await fa.flights_search(f'-idents "{fn}"')
    #     log.debug(fdata)
    #     if not fdata or 'flights' not in fdata or not fdata['flights']:
    #         msg = f'No active flights found for flight number: **{fn}**\n' \
    #               f'_Note: Try using the ICAO Flight Number._'
    #         await ctx.reply(msg)
    #         return
    #     n = len(fdata['flights'])
    #     d = fdata['flights'][0]
    #     msg = (
    #         f"Found {n} Flights: **{fn}** `{d['fa_flight_id']}`\n"
    #         f"```"
    #         f"Aircraft: {d['aircraft_type']}\n"
    #         f"Takeoff:  {d['actual_off']}\n"
    #         f"From:     {d['origin']['code']} - {d['origin']['name']}\n"
    #         f"To:       {d['destination']['code']} - {d['destination']['name']}\n"
    #         f"Speed:    {d['last_position']['groundspeed']}\n"
    #         f"Heading:  {d['last_position']['heading']}\n"
    #         f"FL:       {d['last_position']['altitude']}\n"
    #         f"Lat:      {d['last_position']['latitude']}\n"
    #         f"Long:     {d['last_position']['longitude']}\n"
    #         f"```"
    #     )
    #     await ctx.reply(msg)


class ButtonsURLView(discord.ui.View):
    """URL Button View"""
    def __init__(self, buttons: dict[str, str]):
        super().__init__()
        for label, url in buttons.items():
            self.add_item(discord.ui.Button(label=label, url=url))


class EmbedsView(discord.ui.View):
    """Embeds View"""
    def __init__(self, cog: Flightaware, embeds, oper_icao: str, index: int = 0, timeout: int = 60*60*2):
        self.cog = cog
        self.embeds: List[discord.Embed] = embeds
        self.oper_icao: str = oper_icao
        self.index: int = index
        self.user_id: Optional[int] = None
        self.message: Optional[discord.Message] = None
        super().__init__(timeout=timeout)

    async def send_initial_message(self, ctx, author, content: str = None, index: Optional[int] = None, **kwargs) -> discord.Message:
        log.debug('send_initial_message')
        self.user_id = author.id
        self.index = index if index else self.index
        self.message = await ctx.send(content, view=self, embed=self.embeds[self.index], **kwargs)
        return self.message

    async def on_timeout(self):
        for child in self.children:
            child.style = discord.ButtonStyle.gray
            child.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label='Prev', style=discord.ButtonStyle.green)  # 👈 \U0001F448
    async def prev_button(self, interaction, button):
        # await self.disable_enable_btns(interaction)
        if self.index < 1:
            await interaction.response.edit_message()
            return
        self.index = self.index - 1
        await interaction.response.edit_message(embed=self.embeds[self.index])

    @discord.ui.button(label='Next', style=discord.ButtonStyle.green)  # 👉 \U0001F449
    async def next_button(self, interaction, button):
        # await self.disable_enable_btns(interaction)
        if not self.index < len(self.embeds) - 1:
            await interaction.response.edit_message()
            return
        self.index = self.index + 1
        await interaction.response.edit_message(embed=self.embeds[self.index])

    @discord.ui.button(label='Delete', style=discord.ButtonStyle.red)
    async def delete_button(self, interaction, button):
        if not interaction.user.id == self.user_id:
            await interaction.response.send_message("Looks like you didn't create this response.", ephemeral=True, delete_after=10)
            return
        await interaction.message.delete()
        await interaction.response.send_message('Your wish is my command!', ephemeral=True, delete_after=10)

    # async def disable_enable_btns(self, interaction):
    #     log.debug('self.index: %s', self.index)
    #     log.debug('len(self.embeds): %s', len(self.embeds))
    #     if self.index == 0:
    #         for child in self.children:
    #             if child.label == 'Prev':
    #                 log.debug('-- DISABLE PREV --')
    #                 child.disabled = True
    #                 # await interaction.response.edit_message()
    #     if len(self.embeds) == (self.index-1):
    #         for child in self.children:
    #             if child.label == 'Next':
    #                 log.debug('-- DISABLE NEXT --')
    #                 child.disabled = True
    #                 # await interaction.response.edit_message()

    # @discord.ui.button(label='Operator', style=discord.ButtonStyle.blurple)
    # async def operator_button(self, interaction, button):
    #     button.disabled = True
    #     button.style = discord.ButtonStyle.grey
    #     await interaction.response.edit_message(view=self)
    #
    #     ctx = await self.bot.get_context(interaction.message)
    #     ctx.command = self.bot.get_command('fa_operator')
    #
    #     if ctx.command:
    #         ctx.args = (self.oper_icao,)
    #         await self.bot.get_cog('CommandDispatcher').execute_command(ctx).bot.get_cog('Red').data_manager.invoke_command(ctx)


# class FlightView(discord.ui.View):
#     """Flight View"""
#     def __init__(self, cog: Flightaware, icao: str, buttons: Optional[dict] = None):
#         self.cog = cog
#         self.icao = icao
#         self.buttons = buttons
#         self.message: Optional[discord.Message] = None
#         super().__init__(timeout=60*60*2)
#         if self.buttons:
#             for label, url in self.buttons.items():
#                 self.add_item(discord.ui.Button(label=label, url=url))
#
#     async def on_timeout(self):
#         child: discord.ui.View
#         for child in self.children:
#             if child.label == 'Operator Info':
#                 child.disabled = True
#         await self.message.edit(view=self)
#
#     @discord.ui.button(emoji='\N{AIRPLANE}', label='Operator Info', style=discord.ButtonStyle.blurple)
#     async def button_callback(self, interaction, button):
#         button.disabled = True
#         await interaction.response.edit_message(view=self)
#         await self.cog.fa_operator(interaction.channel, self.icao)