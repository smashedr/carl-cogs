import asyncio
import base64
import discord
import json
import logging
import re
import io
import redis.asyncio as redis
from datetime import timedelta
from typing import Optional, List, Tuple, Dict

from redbot.core import commands
from redbot.core.utils import chat_formatting as cf

from .fa import FlightAware

log = logging.getLogger('red.captcha')


class Flightaware(commands.Cog):
    """Carl's FlightAware Cog"""

    def __init__(self, bot):
        self.bot = bot
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
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    # @commands.Cog.listener(name='on_message_without_command')
    # async def on_message_without_command(self, message: discord.Message):
    #     if message.author.bot:
    #         return
    #     if not message.content:
    #         return
    #     # split = message.content.split()
    #     # if len(split) > 1:
    #     #     return
    #     # word = split[0].upper()
    #     # m = re.search('[a-zA-Z]{2,3}[0-9]{1,4}', message.content)
    #
    #
    #     m = re.search('[a-zA-Z0-9]{2,3}[0-9]{1,4}', message.content)
    #     log.debug(0)
    #     if not m or not m.group(0):
    #         log.debug(1)
    #         return
    #     fn = m.group(0).upper()
    #     log.debug('FN: %s', fn)
    #
    #     valid = False
    #     m = re.search('[a-zA-Z]{3}[0-9]{1,4}', fn)
    #     if m and m.group(0):
    #         log.debug('ICAO')
    #         file = '/data/cogs/flightaware/icao.txt'
    #         with open(file) as f:
    #             if fn[:3] in f.read():
    #                 valid = True
    #     if not valid:
    #         log.debug('IATA')
    #         file = '/data/cogs/flightaware/iata.txt'
    #         with open(file) as f:
    #             if fn[:2] in f.read():
    #                 valid = True
    #     if not valid:
    #         log.error('FN Matched but NOT Found...')
    #         return
    #     log.debug('matched fn to ac')
    #     await self.process_flight(message, fn)
    #
    #
    #     # m = re.search('[a-zA-Z]{2,3}', fn)
    #     # if not m or not m.group(0):
    #     #     log.error('Matched word but not FN')
    #     #     return
    #     # ac = m.group(0)
    #     # log.debug(ac)
    #     # if len(ac) == 2:
    #     #     file = '/data/cogs/flightaware/iata.txt'
    #     # else:
    #     #     file = '/data/cogs/flightaware/icao.txt'
    #     # with open(file) as f:
    #     #     if ac not in f.read():
    #     #         return

    @commands.command(name='flight')
    async def flight(self, ctx: commands.Context, ident: str):
        """Get Flight Information for: <ident>"""
        await self.process_flight(ctx, ident)

    @commands.group(name='flightaware', aliases=['fa'])
    @commands.guild_only()
    async def fa(self, ctx: commands.Context):
        """FlightAware Commands."""

    @fa.command(name='flight', aliases=['f'])
    async def fa_flight(self, ctx: commands.Context, ident_str: str):
        """Get Flight info for: <ident>"""
        await self.process_flight(ctx, ident_str)

    async def process_flight(self, ctx, ident_str: str):
        ident = self.validate_ident(ident_str)
        if not ident:
            await ctx.send(F'Unable to validate `ident`: **{ident_str}**')
            return

        fa = FlightAware(self.api_key)
        fdata = json.loads(await self.client.get(f'fa:{ident}') or '{}')
        if not fdata:
            log.info('--- API CALL ---')
            fdata = await fa.flights_ident(ident)
            log.debug(fdata)
            if not fdata or 'flights' not in fdata or not fdata['flights']:
                msg = f'No flights found for ident: **{ident}**\n'
                await ctx.send(msg)
                return
            await self.client.setex(
                f'fa:{ident}',
                timedelta(minutes=10),
                json.dumps(fdata),
            )

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
            em = discord.Embed()
            em.title = d['fa_flight_id']
            msgs = []
            if d['progress_percent'] and (0 < d['progress_percent'] < 100):
                index = i
                msgs.append(f'🔴 [Live Now on FlightAware]({fa.fa_flight_url}{ident})')
            msgs.append(
                f"```"
                f"Operator:   {d['operator_icao']} / {d['operator_iata']}\n"
                f"ICAO/IATA:  {d['ident_icao']} / {d['ident_iata']}\n"
                f"Status:     {d['status']}\n"
                f"Distance:   {d['route_distance']} nm - {d['progress_percent']}%\n"
                f"Aircraft:   {d['aircraft_type']} - {d['registration']}"
            )
            if d['origin'] and d['destination']:
                msgs.append(
                    f"\nTakeoff:    {d['actual_off']}\n"
                    f"From:       {d['origin']['code']} - {d['origin']['name']}\n"
                    f"ETA:        {d['estimated_on']}\n"
                    f"To:         {d['destination']['code']} - {d['destination']['name']}"
                )
            if d['gate_destination'] and d['baggage_claim']:
                msgs.append(f"\nGate/Bags:  {d['gate_destination']} / {d['baggage_claim']}")
            elif d['gate_destination']:
                msgs.append(f"\nGate:       {d['gate_destination']}")
            elif d['route']:
                msgs.append(f"\nRoute:      {d['route']}")
            if d['codeshares']:
                msgs.append(f"\nCodeshares: {cf.humanize_list(d['codeshares'])}")
            msgs.append(f"```")
            # if d['progress_percent'] and (0 < d['progress_percent'] < 100):
            #     index = i
            #     msgs.append(f'✈️ [Live Now on FlightAware]({fa.fa_flight_url}{ident}) ✈️')

            value = ''
            if d['registration']:
                value += f"[{d['registration']}]({fa.fa_registration_url}{d['registration']}) | "
            if d['aircraft_type']:
                value += f"[{d['aircraft_type']}]({fa.fa_aircraft_url}{d['aircraft_type']}) | "
            if d['origin'] and d['origin']['code_icao']:
                value += f"[{d['origin']['code_icao']}]({fa.fa_airport_url}{d['origin']['code_icao']}) | "
            if d['destination'] and d['destination']['code_icao']:
                value += f"[{d['destination']['code_icao']}]({fa.fa_airport_url}{d['destination']['code_icao']}) | "
            value = value.strip('| ')
            value += f"\n{i+1}/{len(fdata['flights'])}"
            em.add_field(name='Links', value=value)

            # msgs.append(f"{i+1}/{len(fdata['flights'])}")
            em.description = ' '.join(msgs)
            embeds.append(em)

        log.debug('embeds: %s', len(embeds))
        log.debug('index: %s', index)

        view = EmbedsView(self, embeds, index=index)
        await view.send_initial_message(ctx, content=content)

    @fa.command(name='operator', aliases=['airline', 'oper', 'o', 'a'])
    async def fa_operator(self, ctx: commands.Context, airline_id: str):
        """Get Airline Operator info for: <id>"""
        log.debug('airline_id: %s', airline_id)
        operator_id = self.validate_ident(airline_id)
        log.debug('operator_id: %s', operator_id)
        if not operator_id:
            await ctx.send(F'Unable to validate `id`: **{airline_id}**')
            return

        fa = FlightAware(self.api_key)
        fdata = json.loads(await self.client.get(f'fa:{operator_id}') or '{}')
        log.debug(fdata)
        if not fdata:
            log.info('--- API CALL ---')
            fdata = await fa.operators_id(operator_id)
            log.debug(fdata)
        if not fdata:
            await ctx.send('Nothing Found. All the people committed suicide...')
            return

        await self.client.setex(
            f'fa:{operator_id}',
            timedelta(days=7),
            json.dumps(fdata),
        )
        d = fdata
        msgs = [(
            f"Operator: **{d['name']}** "
            f"```"
            f"ICAO/IATA:  {d['icao']} / {d['iata']}\n"
            f"Callsign:   {d['callsign']}\n"
            f"Short:      {d['shortname']}\n"
            f"Country:    {d['country']}"
        )]
        if d['location']:
            msgs.append(f"\nLocation:   {d['location']}")
        if d['phone']:
            msgs.append(f"\nPhone:      {d['phone']}")
        msgs.append(f"```")
        buttons = {}
        if d['url']:
            buttons.update({'Website': d['url']})
        if d['wiki_url']:
            buttons.update({'Wikipedia': d['wiki_url']})
        await ctx.send(' '.join(msgs), view=ButtonsURLView(buttons))

    @staticmethod
    def validate_ident(ident: str):
        # m = re.search('[a-zA-Z0-9]{2,3}[0-9]{1,4}', ident.upper())
        m = re.search('[a-zA-Z0-9-]{2,7}', ident.upper())
        if m and m.group(0):
            return m.group(0)
        return None

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


class FlightView(discord.ui.View):
    """Flight View"""
    def __init__(self, cog: Flightaware, icao: str, buttons: Optional[dict] = None):
        self.cog = cog
        self.icao = icao
        self.buttons = buttons
        self.message: Optional[discord.Message] = None
        super().__init__(timeout=60*60*6)
        if self.buttons:
            for label, url in self.buttons.items():
                self.add_item(discord.ui.Button(label=label, url=url))

    async def on_timeout(self):
        child: discord.ui.View
        for child in self.children:
            if child.label == 'Operator Info':
                child.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(emoji='\N{AIRPLANE}', label="Operator Info", style=discord.ButtonStyle.blurple)
    async def button_callback(self, interaction, button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await self.cog.fa_operator(interaction.channel, self.icao)


class EmbedsView(discord.ui.View):
    """Embeds View"""
    def __init__(self, cog: Flightaware, embeds, index: int = 0, timeout: int = 60*60*6):
        self.cog: commands.Cog = cog
        self.embeds: List[discord.Embed] = embeds
        self.index: int = index
        self.user_id: Optional[int] = None
        self.message: Optional[discord.Message] = None
        super().__init__(timeout=timeout)

    async def send_initial_message(self, ctx, content: str = None,
                                   index: Optional[int] = None, **kwargs) -> discord.Message:
        log.debug('send_initial_message')
        self.user_id = ctx.author.id
        self.index = index if index else self.index
        self.message = await ctx.send(content, view=self, embed=self.embeds[self.index], **kwargs)
        return self.message

    async def on_timeout(self):
        for child in self.children:
            child.style = discord.ButtonStyle.gray
            child.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label='Prev', style=discord.ButtonStyle.blurple)
    async def prev_button(self, interaction, button):
        if self.index < 1:
            await interaction.response.edit_message()
            return
        self.index = self.index - 1
        await interaction.response.edit_message(embed=self.embeds[self.index])

    @discord.ui.button(label='Next', style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction, button):
        if not self.index < len(self.embeds) - 1:
            await interaction.response.edit_message()
            return
        self.index = self.index + 1
        await interaction.response.edit_message(embed=self.embeds[self.index])


#
# GARBAGE BELOW
#


# class GetOperatorButton(discord.ui.Button):
#     def __init__(self, cog: commands.Cog):
#         super().__init__(
#             emoji='\N{AIRPLANE}',
#             label='Get Operator Info',
#             style=discord.ButtonStyle.green,
#             # custom_id='captcha-url-btn',
#         )
#         self.cog = cog
#
#     async def callback(self, interaction: discord.Interaction):
#         log.debug('-'*40)
#         tolog = interaction
#         log.debug(dir(tolog))
#         log.debug(type(tolog))
#         log.debug(tolog)
#         # params = {
#         #     'user': interaction.user.id,
#         #     'guild': interaction.guild.id,
#         # }
#         # query_string = urlencode(params)
#         # url = f'{self.cog.url}/verify/?{query_string}'
#         # message = f'{interaction.user.mention} Click Here: <{url}>'
#
#         # self.disabled = True # set button.disabled to True to disable the button
#         # self.label = "No more pressing!" # change the button's label to something else
#         # await interaction.response.edit_message(view=self)
#
#         msg = 'It Happened, Late at Night.'
#         await interaction.response.send_message(msg, ephemeral=True,
#                                                 delete_after=180)
