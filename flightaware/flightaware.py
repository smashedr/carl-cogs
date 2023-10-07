import discord
import httpx
import json
import logging
import pathlib
import re
import redis.asyncio as redis
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from html import unescape
from typing import List, Optional, Union

from redbot.core import commands, app_commands, Config
from redbot.core.bot import Red
from redbot.core.utils import chat_formatting as cf

from .fa import FlightAware

log = logging.getLogger('red.flightaware')


class Flightaware(commands.Cog):
    """Carl's FlightAware Cog"""

    guild_default = {
        'enabled': True,
    }

    def __init__(self, bot):
        self.bot: Red = bot
        self.api_key: Optional[str] = None
        self.redis: Optional[redis.Redis] = None
        self.cog_dir = pathlib.Path(__file__).parent.resolve()
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data = await self.bot.get_shared_api_tokens('flightaware')
        self.api_key = data.get('api_key') or data.get('token')
        if not self.api_key:
            raise ValueError('Missing flightaware token. Use the "set api" command.')
        redis_data: dict = await self.bot.get_shared_api_tokens('redis')
        self.redis = redis.Redis(
            host=redis_data.get('host', 'redis'),
            port=int(redis_data.get('port', 6379)),
            db=int(redis_data.get('db', 0)),
            password=redis_data.get('pass', None),
        )
        await self.redis.ping()
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
        if not (3 <= len(message.content) <= 7):
            return
        split: list = message.content.split()
        if len(split) > 1:
            return
        m = re.search('[a-zA-Z0-9]{2,3}[0-9]{1,4}', split[0].upper())
        if not m or not m.group(0):
            return

        if not await self.config.guild(message.guild).enabled():
            return log.debug('%s: Disabled', self.__cog_name__)

        fn = m.group(0).upper()
        log.debug('FN: %s', fn)
        m = re.search('[a-zA-Z]{2,3}[0-9]{1,4}', fn)
        if not m or not m.group(0):
            return

        valid = False
        file = f'{self.cog_dir}/icao.txt'
        with open(file) as f:
            if fn[:3] in f.read():
                valid = True
                log.debug('ICAO')
        if not valid:
            file = f'{self.cog_dir}/iata.txt'
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

    @fa.command(name='toggle', aliases=['enable', 'disable', 'on', 'off'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def fa_toggle(self, ctx: commands.Context):
        """Enable/Disable FlightAware Auto Parsing"""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await self.config.guild(ctx.guild).enabled.set(False)
            return await ctx.send(f'\U0001F6D1 {self.__cog_name__} Disabled.')
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(f'\U00002705 {self.__cog_name__} Enabled.')

    @fa.command(name='flight', description='Get Flight Information')
    @app_commands.describe(ident='Flight Number or Registration Number')
    async def fa_flight(self, ctx: commands.Context, ident: str):
        """Get Flight Information for: <ident>"""
        await self.process_flight(ctx, ctx.author, ident)

    async def process_flight(self, sendable: Union[commands.Context, discord.TextChannel],
                             author: Union[discord.Member, discord.User],
                             ident_str: str, silent=False):
        ident: str = self.validate_ident(ident_str)
        if not ident:
            if silent:
                return
            msg = f'Unable to validate `ident`: **{ident_str}**'
            return await sendable.send(msg, ephemeral=True, delete_after=15)
        # TODO: Move this to init
        fa = FlightAware(self.api_key)
        fdata: dict = json.loads(await self.redis.get(f'fa:{ident}') or '{}')
        if not fdata:
            log.info('--- API CALL ---')
            fdata = await fa.flights_ident(ident)
            log.debug(fdata)
            await self.redis.setex(
                f'fa:{ident}',
                timedelta(minutes=55),  # TODO: DO NOT COMMIT DO NOT COMMIT DO NOT COMMIT DO NOT COMMIT DO NOT COMMIT DO NOT COMMIT DO NOT COMMIT
                json.dumps(fdata or {}),
            )
        if 'flights' not in fdata or not fdata['flights']:
            if silent:
                return
            msg = f'No flights found for ident: **{ident}**\n'
            return await sendable.send(msg, ephemeral=True, delete_after=15)

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
        #     await sendable.send(' '.join(msgs))
        #     return

        embeds = []
        index = 0
        content = f'Flights found for **{ident}**'
        for i, d in enumerate(reversed(fdata['flights'])):
            live = False
            id_url = f"{fa.fa_id_url}{d['fa_flight_id']}"
            flight_url = f"{fa.fa_flight_url}{d['ident']}"

            em = discord.Embed(
                title=f"{d['ident_icao']} / {d['ident_iata']}",
                url=flight_url,
            )
            em.set_author(name=d['fa_flight_id'], url=id_url)

            if not d['actual_off']:
                em.colour = discord.Colour.blue()
            elif d['actual_off'] and not d['actual_on']:
                em.colour = discord.Colour.green()
                live = True
                index = i
                log.debug('set index on (actual_off and not actual_on)')
            else:
                em.colour = discord.Colour.light_gray()

            if not index and d['progress_percent'] and 0 < d['progress_percent'] < 100:
                em.colour = discord.Colour.green()
                live = True
                index = i
                log.debug('set index on (0 < progress_percent < 100)')
                # msgs.append(f'🟢 [Live Now on FlightAware]({fa.fa_flight_url}{ident}) ')
            # if d['actual_off'] and d['actual_on'] and (d['actual_off'] == d['actual_on']):
            # if d['status'] and 'scheduled' in d['status'].lower():
            #     em.colour = discord.Colour.blue()

            if live:
                log.debug('LIVE '*5)

            out = d['scheduled_out'] or d['estimated_out'] or d['actual_out']
            off = d['scheduled_off'] or d['estimated_off'] or d['actual_off']
            _on = d['scheduled_on'] or d['estimated_on'] or d['actual_on']
            _in = d['scheduled_in'] or d['estimated_in'] or d['actual_in']

            out_dt = datetime.strptime(out, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=None) if out else None
            off_dt = datetime.strptime(off, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=None) if off else None
            depart_dt = out_dt or off_dt
            on_dt = datetime.strptime(_on, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=None) if _on else None
            in_dt = datetime.strptime(_in, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=None) if _in else None
            # arrive_dt = on_dt or in_dt

            em.timestamp = out_dt or off_dt or in_dt or on_dt
            if not index and depart_dt and datetime.now() < depart_dt:
                index = i
                log.debug('set index on DATETIME: %s', index)

            msgs = []

            if d['position_only']:
                msgs.append('🔵 **Position Only**\n')
            if d['cancelled']:
                msgs.append('🔴 **Cancelled**\n')
            if d['blocked']:
                msgs.append('🟠 **Blocked**\n')
            if d['diverted']:
                msgs.append('🟡 **Diverted**\n')

            flight_link = f"[{d['ident']}]({id_url})"
            oper_link = f"[{d['operator']}]({fa.fa_fleet_url}{d['operator']})"

            msgs.append(f'Flight **{flight_link}** is operated by **{oper_link}**')
            # msgs.append(f'Operator: **{oper_link}**')
            # msgs.append(f"Flight: **{flight_link}**")
            # msgs.append(
            #     f"Flight **{flight_link}** "
            #     f"Operated by **{oper_link}** "
            #     f"and sold as {cf.humanize_list(d['codeshares'])}"
            # )
            if d['codeshares']:
                shares = [f'`{x}`' for x in d['codeshares']]
                msgs.append(f"Codeshares {cf.humanize_list(shares)}")

            msgs.append(f"\n**{d['status']}**")
            # msgs.extend([
            #     f"Flight **{flight_link}**",
            #     f"Status: **{d['status']}**",
            # ])

            # if d['route']:
            #     # if not d['route'].startswith(d['origin']['code_icao']):
            #     #     d['route'] = f"{d['origin']['code_icao']} {d['route']}"
            #     msgs.append(f"```\n{d['route']}```")

            if d['aircraft_type']:
                links = await self.aircraft_type_links(d, fa)
                msgs.append(f"\n**{d['aircraft_type']}** - {links}")

            if d['registration']:
                links = await self.aircraft_reg_links(d, fa)
                msgs.append(f"**{d['registration']}** - {links}")

            if d['origin']:
                origin_link = f"[{d['origin']['code']}]({fa.fa_airport_url}{d['origin']['code']})"
                msgs.extend([
                    "",
                    f"\U0001F6EB **{origin_link} {d['origin']['name']}**",
                    f"Depart: {self.get_ts(out_dt)}",
                    f"Takeoff: {self.get_ts(off_dt)}",
                    self.airport_links(d['origin']['code_icao'], fa),
                ])

            if d['destination']:
                destination_link = f"[{d['destination']['code']}]({fa.fa_airport_url}{d['destination']['code']})"
                msgs.extend([
                    "",
                    f"\U0001F6EC **{destination_link} {d['destination']['name']}**",
                    f"Touchdown: {self.get_ts(on_dt)}",
                    f"Arrival: {self.get_ts(in_dt)}",
                    self.airport_links(d['destination']['code_icao'], fa),
                ])
                # if d['gate_destination'] or d['baggage_claim']:
                #     msgs.append(f"**Gate/Bags**:  {d['gate_destination']} / {d['baggage_claim']}")

            em.description = '\n'.join(msgs)

            if d['terminal_destination']:
                em.add_field(name='Terminal', value=f"{d['terminal_destination']}")
            if d['gate_destination']:
                em.add_field(name='Gate', value=f"{d['gate_destination']}")
            if d['baggage_claim']:
                em.add_field(name='Baggage', value=f"{d['baggage_claim']}")

            if d['route_distance']:
                em.add_field(name='Distance', value=f"{d['route_distance']} nm")
            if d['filed_altitude']:
                em.add_field(name='Altitude', value=f"FL {d['filed_altitude']}")
            if d['filed_airspeed']:
                em.add_field(name='Speed', value=f"{d['filed_airspeed']} kn")

            if d['route']:
                # if not d['route'].startswith(d['origin']['code_icao']):
                #     d['route'] = f"{d['origin']['code_icao']} {d['route']}"
                em.add_field(name='Route', value=f"```{d['route']}```", inline=False)

            # oper_icao = d['operator_icao'] or d['operator'] or d['operator_iata']

            # matches = ['on the way', 'en route', 'taxiing']
            # if (d['progress_percent'] and (0 < d['progress_percent'] < 100)) \
            #         or any([x in d['status'].lower() for x in matches]):
            #     index = i
            #     log.debug('set index on PROGRESS or MATCH')
            #     msgs.append(f'🟢 [Live Now on FlightAware]({fa.fa_flight_url}{ident}) ')
            #     em.colour = discord.Colour.green()

            # msgs.extend([
            #     "```ini",
            #     f"[ICAO/IATA]:  {d['ident_icao']} / {d['ident_iata']}",
            #     f"[Operator]:   {d['operator_icao']} / {d['operator_iata']}",
            # ])
            # if d['codeshares']:
            #     msgs.append(f"[Codeshares]: {cf.humanize_list(d['codeshares'])}")
            # msgs.extend([
            #     f"[Status]:     {d['status']}",
            #     f"[Distance]:   {d['route_distance']} nm / {d['progress_percent']}%",
            #     f"[Aircraft]:   {d['aircraft_type']} / {d['registration']}",
            # ])
            # if d['filed_airspeed'] or d['filed_altitude']:
            #     msgs.append(f"[Speed/Alt]:  {d['filed_airspeed']} kn / FL {d['filed_altitude']}")
            # if d['route']:
            #     if not d['route'].startswith(d['origin']['code_icao']):
            #         d['route'] = f"{d['origin']['code_icao']} {d['route']}"
            #     msgs.append(f"[Route]:      {d['route']}")
            # msgs.append('')
            # if d['origin'] and d['destination']:
            #     msgs.append(f"[From]:       {d['origin']['code']} / {d['origin']['name']}")
            #     if out:
            #         msgs.append(f"[Departs]:    {off}")
            #     if off:
            #         msgs.append(f"[Takeoff]:    {off}")
            #     msgs.append('')
            #     msgs.append(f"[To]:         {d['destination']['code']} / {d['destination']['name']}")
            #     if _on:
            #         msgs.append(f"[Landing]:    {_on}")
            #     if _in:
            #         msgs.append(f"[Arrival]:    {_in}")
            # if d['gate_destination'] or d['baggage_claim']:
            #     msgs.append(f"[Gate/Bags]:  {d['gate_destination']} / {d['baggage_claim']}")
            # # msgs.append(
            # #     f"[Speed/Alt]:  {d['filed_airspeed']}/{d['filed_altitude']}\n"
            # #     f"[From]:       {d['origin']['code']} / {d['origin']['name']}\n"
            # # )
            # msgs.append("```")
            # msgs = '\n'.join(msgs)

            # value = ''
            # if d['registration']:
            #     value += f"[{d['registration']}]({fa.fa_registration_url}{d['registration']}) " \
            #              f"[🖼️]({fa.jetphotos_url}{d['registration']}) | "
            # if d['aircraft_type']:
            #     wiki_url = await self.get_wiki_url(d['aircraft_type'])
            #     if wiki_url:
            #         value += f"[{d['aircraft_type']}]({wiki_url}) | "
            #     else:
            #         value += f"{d['aircraft_type']} | "
            # if d['origin'] and d['origin']['code_icao']:
            #     value += f"[{d['origin']['code_icao']}]({fa.airnav_url}{d['origin']['code_icao']}) " \
            #              f"[🔈]({fa.liveatc_url}{d['origin']['code_icao']}) | "
            # if d['destination'] and d['destination']['code_icao']:
            #     value += f"[{d['destination']['code_icao']}]({fa.airnav_url}{d['destination']['code_icao']}) " \
            #              f"[🔈]({fa.liveatc_url}{d['destination']['code_icao']}) | "
            # value = value.strip('| ')
            # # value += f"\n{i+1}/{len(fdata['flights'])}"
            # em.add_field(name='Links', value=value)

            em.set_footer(text=f"{i+1}/{len(fdata['flights'])}")
            # msgs.append(f"{i+1}/{len(fdata['flights'])}")
            embeds.append(em)
        log.debug('embeds: %s', len(embeds))
        log.debug('index: %s', index)
        view = EmbedsView(self, author, embeds, index)
        await view.send_initial_message(sendable, content=content)

    @fa.command(name='operator', description='Airline Operator Information')
    @app_commands.describe(code='Airline ICAO or IATA Identifier')
    async def fa_operator(self, ctx: commands.Context, code: str):
        """Get Airline Operator info for: <id>"""
        log.debug('code: %s', code)
        operator_id = self.validate_ident(code)
        log.debug('operator_id: %s', operator_id)
        if not operator_id:
            msg = f'Unable to validate `id`: **{code}**'
            return await ctx.send(msg, ephemeral=True, delete_after=10)

        fa = FlightAware(self.api_key)
        fdata = json.loads(await self.redis.get(f'fa:{operator_id}') or '{}')
        log.debug(fdata)
        if not fdata:
            log.info('--- API CALL ---')
            fdata = await fa.operators_id(operator_id)
            log.debug(fdata)
        if not fdata:
            msg = f'No results for operator id: `{operator_id}`'
            return await ctx.send(msg, ephemeral=True, delete_after=10)

        await self.redis.setex(f'fa:{operator_id}', timedelta(days=30), json.dumps(fdata))
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
        msgs.append("```")
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
            return await ctx.send(f'Unable to validate `id`: **{ident}**', ephemeral=True, delete_after=10)

        fa = FlightAware(self.api_key)
        fdata = json.loads(await self.redis.get(f'fa:{identifier}') or '{}')
        log.debug(fdata)
        if not fdata:
            log.info('--- API CALL ---')
            fdata = await fa.owner_ident(identifier)
            log.debug(fdata)
        if not fdata:
            return await ctx.send(f'No results for ident: `{identifier}`', ephemeral=True, delete_after=10)

        await self.redis.setex(f'fa:{identifier}', timedelta(days=30), json.dumps(fdata))
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
        base_url = 'https://en.wikipedia.org'
        try:
            aircraft_data: dict = json.loads(await self.redis.get('fa:wiki_aircraft_type') or '{}')
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
        url = 'https://en.wikipedia.org/wiki/List_of_aircraft_type_designators'
        http_options = {
            'follow_redirects': True,
            'timeout': 30,
        }
        async with httpx.AsyncClient(**http_options) as client:
            r = await client.get(url)
            r.raise_for_status()
        html = r.text
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
        # log.debug('-'*20)
        # log.debug(aircraft_data)
        await self.redis.setex(
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

    async def _get_icao_hex(self, registration: str) -> Optional[str]:
        cache: str = await self.redis.get(f'pdb:{registration}')
        if cache:
            log.debug('cache: %s', cache)
            log.debug('cache.type: %s', type(cache))
            return cache
        registration = registration.replace('-', '').upper()
        if registration.startswith('N'):
            reg_type = '0'
        elif registration.startswith('C'):
            reg_type = '1'
        else:
            return None
        url = 'https://www.avionictools.com/icao.php'
        data = {
            'type':	reg_type,
            'data':	registration,
            'strap': '0',
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, data=data)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        td_elements = soup.find_all('td')
        for td in td_elements:
            if 'Hex:' in td.text:
                hex_value = td.contents[2]
                break
        else:
            return None
        hex_value = hex_value.split()[1].lower()
        await self.redis.set(
            f'pdb:{registration}',
            hex_value,
            timedelta(minutes=60*24*7),
        )
        log.debug('hex_value: %s', hex_value)
        log.debug('hex_value.type: %s', type(hex_value))
        return hex_value

    @staticmethod
    def airport_links(code_icao: str, fa: FlightAware) -> str:
        links = [
            f"[LiveATC]({fa.liveatc_url}{code_icao})",
            f"[AirNav]({fa.airnav_url}{code_icao})",
        ]
        return ' | '.join(links)

    async def aircraft_type_links(self, d: dict, fa: FlightAware) -> str:
        if not d['aircraft_type']:
            return ''
        links = []
        links.append(f"[FA]({fa.fa_aircraft_url}{d['aircraft_type']})")
        if wiki_url := await self.get_wiki_url(d['aircraft_type']):
            links.append(f"[Wikipedia]({wiki_url})")
        return ' | '.join(links)

    async def aircraft_reg_links(self, d: dict, fa: FlightAware) -> str:
        if not d['registration']:
            return ''
        links = []
        if d['registration']:
            links.append(f"[FA]({fa.fa_registration_url}{d['registration']})")
            links.append(f"[FR24]({fa.fr24_reg_url}{d['registration']})")
            # TODO: Only do this on live flight
            # if icao_hex := await self._get_icao_hex(d['registration']):
            #     links.append(f"[ADSBE](https://globe.adsbexchange.com/?icao={icao_hex})")
            links.append(f"[AirFleets]({fa.airfleets_search_url}{d['registration']})")
            links.append(f"[JetPhotos]({fa.jetphotos_url}{d['registration']})")
        return ' | '.join(links)

        # if not d['registration'] and d['aircraft_type']:
        #     return ''
        # links = []
        # wiki_url = await self.get_wiki_url(d['aircraft_type']) if d['aircraft_type'] else None
        # if not d['registration']:
        #     links.append(f"[Wikipedia]({wiki_url})")
        # data = ' | '.join(links)
        # log.debug('data: %s', data)
        # return data

    @staticmethod
    def get_ts(ts: Optional[datetime], fmt='F') -> str:
        if not ts:
            return '_Unknown_'
        return f'<t:{int(ts.timestamp())}:{fmt}>'


class ButtonsURLView(discord.ui.View):
    """URL Button View"""
    def __init__(self, buttons: dict[str, str]):
        super().__init__()
        for label, url in buttons.items():
            self.add_item(discord.ui.Button(label=label, url=url))


class EmbedsView(discord.ui.View):
    """Embeds View"""
    def __init__(self, cog,
                 author: Union[int, discord.Member, discord.User],
                 embeds: List[discord.Embed],
                 # oper_icao: str,
                 index: int = 0,
                 timeout: int = 60*60*2):
        self.cog: Flightaware = cog
        self.user_id: int = author.id if hasattr(author, 'id') else int(author)
        self.embeds: List[discord.Embed] = embeds
        # self.oper_icao: str = oper_icao
        self.index: int = index
        self.message: Optional[discord.Message] = None
        self.owner_only_sec: int = 120
        self.created_at = datetime.now()
        super().__init__(timeout=timeout)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.user_id:
            return True
        td = datetime.now() - self.created_at
        if td.seconds >= self.owner_only_sec:
            return True
        remaining = self.owner_only_sec - td.seconds
        msg = (f"⛔ The creator has control for {remaining} more seconds...\n"
               f"You can create your own response with the `/flight` command.")
        await interaction.response.send_message(msg, ephemeral=True, delete_after=10)
        return False

    async def send_initial_message(self, ctx, index: Optional[int] = None, **kwargs) -> discord.Message:
        self.index = index if index else self.index
        self.message = await ctx.send(view=self, embed=self.embeds[self.index], **kwargs)
        return self.message

    async def on_timeout(self):
        for child in self.children:
            child.style = discord.ButtonStyle.gray
            child.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label='Prev', style=discord.ButtonStyle.green)
    async def prev_button(self, interaction, button):
        # await self.disable_enable_buttons(interaction)
        if self.index < 1:
            return await interaction.response.edit_message()
        self.index = self.index - 1
        await interaction.response.edit_message(embed=self.embeds[self.index])

    @discord.ui.button(label='Next', style=discord.ButtonStyle.green)
    async def next_button(self, interaction, button):
        # await self.disable_enable_buttons(interaction)
        if not self.index < len(self.embeds) - 1:
            return await interaction.response.edit_message()
        self.index = self.index + 1
        await interaction.response.edit_message(embed=self.embeds[self.index])

    @discord.ui.button(label='Delete', style=discord.ButtonStyle.red)
    async def delete_button(self, interaction, button):
        if not interaction.user.id == self.user_id:
            msg = ("⛔ Looks like you didn't create this response.\n"
                   "You can create your own response with the `/history` command.")
            return await interaction.response.send_message(msg, ephemeral=True, delete_after=10)
        await interaction.message.delete()
        await interaction.response.send_message('✅ Your wish is my command!', ephemeral=True, delete_after=10)

    # async def disable_enable_buttons(self, interaction):
    #     log.debug('self.index: %s', self.index)
    #     log.debug('len(self.embeds): %s', len(self.embeds))
    #     if self.index < 1:
    #         d_prev = True
    #     else:
    #         d_prev = False
    #
    #     if not self.index < len(self.embeds) - 1:
    #         d_next = True
    #     else:
    #         d_next = False
    #
    #     for child in self.children:
    #         if child.label == 'Prev':
    #             log.debug('-- Prev - %s --', d_prev)
    #             child.disabled = d_prev
    #         if child.label == 'Next':
    #             log.debug('-- Next - %s --', d_next)
    #             child.disabled = d_next
