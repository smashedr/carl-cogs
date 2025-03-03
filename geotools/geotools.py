import datetime
import discord
import geopy
import logging
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from typing import Any, Dict, Optional, Tuple, Union

from redbot.core import commands

log = logging.getLogger('red.geotools')


class GeoTools(commands.Cog):
    """My custom cog"""

    def __init__(self, bot):
        self.bot = bot
        self.gl = Nominatim(user_agent=self.__cog_name__)
        self.tf = TimezoneFinder()

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.command(name='distance', aliases=['dist'])
    async def _distance(self, ctx: commands.Context, *, location: str):
        log.debug('location: %s', location)
        if ' - ' in location:
            split = location.split(' - ')
        elif ' to ' in location:
            split = location.split(' to ')
        elif ' from ' in location:
            split = location.split(' from ')
        else:
            return await ctx.send('⛔  Need 2 locations, seperated by " - " or " to " or " from "')
        if len(split) != 2:
            return await ctx.send(f'⛔  Need 2 locations, seperated by " to ". Not: `{location}`')

        loc1 = split[0].strip()
        geo1 = self.gl.geocode(loc1)
        if not geo1 or not geo1.latitude or not geo1.longitude:
            return await ctx.send(f'⛔  Error getting Geo Data for: {loc1}')

        loc2 = split[1].strip()
        geo2 = self.gl.geocode(loc2)
        if not geo2 or not geo2.latitude or not geo2.longitude:
            return await ctx.send(f'⛔  Error getting Geo Data for: {loc2}')

        distance = geodesic((geo1.latitude, geo1.longitude), (geo2.latitude, geo2.longitude))
        log.debug(distance)
        embed = discord.Embed(
            title=f"{geo1.raw.get('name', 'Loc 1')} to {geo2.raw.get('name', 'Loc 2')}",
            timestamp=datetime.datetime.now(),
        )
        decimals = 2
        embed.description = '\n'.join([
            f'From: [{geo1}]({self.geohack_url_from_geo(geo1)})',
            f'To: [{geo2}]({self.geohack_url_from_geo(geo2)})',
            '',
            f'US Feet: `{round(distance.feet, decimals)}`\n'
            f'Statute mile: `{round(distance.miles, decimals)}`\n'
            f'Nautical mile: `{round(distance.nm, decimals)}`\n'
            f'Kilometers: `{round(distance.kilometers, decimals)}`\n'
        ])
        await ctx.send(f'Distance from **{geo1}** to **{geo2}**', embed=embed)

    def geohack_url_from_geo(self, geo: geopy.location.Location,
                             name: Optional[str] = None,
                             scale: Optional[str] = '2500000') -> str:
        name = name.replace(' ', '_') if name else geo.raw['display_name'].replace(' ', '_')
        dn, mn, sn = self.dd2dms(geo.latitude)
        dw, mw, sw = self.dd2dms(geo.longitude)
        params = f"{dn}_{mn}_{sn}_N_{dw}_{mw}_{sw}_W_scale:{scale}"
        return f"https://geohack.toolforge.org/geohack.php?pagename={name}&params={params}"

    @staticmethod
    def dd2dms(dd: Union[float, int]) -> Tuple[int, int, int]:
        mult = -1 if dd < 0 else 1
        mnt, sec = divmod(abs(dd)*3600, 60)
        deg, mnt = divmod(mnt, 60)
        return abs(mult*deg), abs(mult*mnt), abs(mult*sec)
