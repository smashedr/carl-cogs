import asyncio
import base64
import discord
import logging
import re
import io

from redbot.core import commands
from redbot.core.utils import chat_formatting as cf

from .fa import FlightAware

log = logging.getLogger('red.captcha')


class Flightaware(commands.Cog):
    """Carl's FlightAware Cog"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)

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
    async def fa_flight(self, ctx: commands.Context, ident: str):
        """Get Flight Information for: <ident>"""
        await self.process_flight(ctx, ident)

    async def process_flight(self, ctx, ident: str):
        ident_validate = self.validate_ident(ident)
        if not ident_validate:
            await ctx.send(F'Unable to validate `ident`: **{ident}**')
            return

        ident = ident_validate
        fa = FlightAware('NKvlLrgaLaXDf4bVLW4ex9OwCf782Aoa')
        fdata = await fa.flights_ident(ident)
        log.debug(fdata)
        if not fdata or 'flights' not in fdata or not fdata['flights']:
            msg = f'No flights found for ident: **{ident}**\n'
            await ctx.send(msg)
            return

        total = len(fdata['flights'])
        log.debug('total: %s', total)
        live, past, sched = [], [], []
        for f in fdata['flights']:
            if int(f['progress_percent']) == 0:
                sched.append(f)
            elif int(f['progress_percent']) == 100:
                past.append(f)
            else:
                live.append(f)
        log.debug('-'*20)
        log.debug('live: %s', len(live))
        log.debug('past: %s', len(past))
        log.debug('sched: %s', len(sched))
        msgs = [f'**{ident}**: Live: `{len(live)}`  Sched: `{len(sched)}`  Past: `{len(past)}`']
        if len(live) > 1 and len(sched) == 0:
            await ctx.send(' '.join(msgs))
            return

        if len(live) == 1:
            f = live[0]
            log.debug(f)
            msgs.append(
                f"\nFA ID: `{f['fa_flight_id']}`\n"
                f"```"
                f"ICAO/IATA:  {f['ident_icao']} / {f['ident_iata']}\n"
                f"Status:     {f['status']} -- {f['progress_percent']}%\n"
                f"Distance:   {f['route_distance']} nm\n"
                f"Aircraft:   {f['aircraft_type']} - {f['registration']}\n"
                f"Takeoff:    {f['actual_off']}\n"
                f"From:       {f['origin']['code']} - {f['origin']['name']}\n"
                f"ETA:        {f['estimated_on']}\n"
                f"To:         {f['destination']['code']} - {f['destination']['name']}"
            )
            if f['gate_destination'] and f['baggage_claim']:
                msgs.append(f"\nGate/Bags:  {f['gate_destination']} / {f['baggage_claim']}")
            elif f['gate_destination']:
                msgs.append(f"\nGate:       {f['gate_destination']}")
            if f['codeshares']:
                msgs.append(f"\nCodeshares: {cf.humanize_list(f['codeshares'])}")
            msgs.append(f"```")
            msgs.append(f'<{fa.live_flight_url}{ident}>')

            # data = await fa.flights_map(f['fa_flight_id'])
            # if 'map' not in data:
            #     await ctx.send(' '.join(msgs))
            #     return
            # image_data = base64.b64decode(data['map'])
            # file_data = io.BytesIO()
            # file_data.write(image_data)
            # file_data.seek(0)
            # file = discord.File(file_data, filename=f"{f['fa_flight_id']}.png")
            # await ctx.send(' '.join(msgs), files=[file])
            # return

        await ctx.send(' '.join(msgs))

    @staticmethod
    def validate_ident(ident: str):
        m = re.search('[a-zA-Z0-9]{2,3}[0-9]{1,4}', ident.upper())
        if m and m.group(0):
            return m.group(0)
        return None

    # async def process_live_flight(self, ctx, ident: str):
    #     fa = FlightAware('NKvlLrgaLaXDf4bVLW4ex9OwCf782Aoa')
    #     fdata = await fa.flights_search(f'-idents "{fn}"')
    #     log.debug(fdata)
    #     if not fdata or 'flights' not in fdata or not fdata['flights']:
    #         msg = f'No active flights found for flight number: **{fn}**\n' \
    #               f'_Note: Try using the ICAO Flight Number._'
    #         await ctx.reply(msg)
    #         return
    #     n = len(fdata['flights'])
    #     f = fdata['flights'][0]
    #     msg = (
    #         f"Found {n} Flights: **{fn}** `{f['fa_flight_id']}`\n"
    #         f"```"
    #         f"Aircraft: {f['aircraft_type']}\n"
    #         f"Takeoff:  {f['actual_off']}\n"
    #         f"From:     {f['origin']['code']} - {f['origin']['name']}\n"
    #         f"To:       {f['destination']['code']} - {f['destination']['name']}\n"
    #         f"Speed:    {f['last_position']['groundspeed']}\n"
    #         f"Heading:  {f['last_position']['heading']}\n"
    #         f"FL:       {f['last_position']['altitude']}\n"
    #         f"Lat:      {f['last_position']['latitude']}\n"
    #         f"Long:     {f['last_position']['longitude']}\n"
    #         f"```"
    #     )
    #     await ctx.reply(msg)
