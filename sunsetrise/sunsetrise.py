import datetime
import discord
import geopy
import httpx
import logging
import pytz
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from typing import Optional, Union, Tuple, Dict, Any

from redbot.core import app_commands, commands

log = logging.getLogger('red.sunsetrise')


class Sunsetrise(commands.Cog):
    """Carl's Sunsetrise Cog"""

    sun_png = 'https://img.cssnr.com/p/20230621-181909363.png'
    moon_png = 'https://img.cssnr.com/p/20230621-181939767.png'

    def __init__(self, bot):
        self.bot = bot
        self.gl = Nominatim(user_agent=self.__cog_name__)
        self.tf = TimezoneFinder()

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.hybrid_command(name='sun', aliases=['sunset', 'sunrise'],
                             description='Get Sun Data for <location>')
    @commands.guild_only()
    @app_commands.describe(location='Location to get SUn Data for')
    async def sun_command(self, ctx: commands.Context, *, location: str):
        """Get Sun Data for <location>"""
        geo = self.gl.geocode(location)
        if not geo or not geo.latitude or not geo.longitude:
            return await ctx.send(f'⛔  Error getting Lat/Lon Data for: {location}')

        tz = self.tf.timezone_at(lat=geo.latitude, lng=geo.longitude)
        timezone = pytz.timezone(tz)
        current_time_utc = datetime.datetime.now(pytz.UTC)
        current_time = current_time_utc.astimezone(timezone)
        data = await self.get_sun_data(geo.latitude, geo.longitude,
                                       date=current_time.strftime('%Y-%m-%d'))
        if data['status'] != 'OK':
            content = (f'⛔  Error getting Sun Data for: {location}\n'
                       f'Lat: `{geo.latitude}` Lon: `{geo.longitude}`')
            return await ctx.send(content)
        embed = discord.Embed(
            title=geo.raw['display_name'],
            url=self.geohack_url_from_geo(geo),
            timestamp=datetime.datetime.now(),
        )
        sunrise_utc = datetime.datetime.fromisoformat(data['results']['sunrise'])
        sunrise = sunrise_utc.astimezone(timezone)
        sunset_utc = datetime.datetime.fromisoformat(data['results']['sunset'])
        sunset = sunset_utc.astimezone(timezone)
        solar_noon_utc = datetime.datetime.fromisoformat(data['results']['solar_noon'])
        solar_noon = solar_noon_utc.astimezone(timezone)
        duration = datetime.timedelta(seconds=int(data['results']['day_length']))
        if sunrise < current_time < sunset:
            embed.colour = discord.Colour.orange()
            embed.set_thumbnail(url=self.sun_png)
            icon = '🌞'
        else:
            embed.colour = discord.Colour.dark_blue()
            embed.set_thumbnail(url=self.moon_png)
            icon = '🌚'
        embed.add_field(name='Sunrise', value=sunrise.strftime('%I:%M:%S %p'))
        embed.add_field(name='Noon', value=solar_noon.strftime('%I:%M:%S %p'))
        embed.add_field(name='Sunset', value=sunset.strftime('%I:%M:%S %p'))
        embed.add_field(name='Day Length', value=str(duration))
        embed.add_field(name='Local Time', value=current_time.strftime('%I:%M:%S %p'))
        embed.add_field(name='Time Zone', value=tz)
        embed.set_author(name=f'Lat: {geo.latitude} / Lon: {geo.longitude}')
        content = f"{icon}  **{location}**"
        await ctx.send(content=content, embed=embed)

    @staticmethod
    async def get_sun_data(lat: float, lon: float, **kwargs) -> Dict[str, Any]:
        _params = {'lat': lat, 'lng': lon, 'formatted': 0}
        if kwargs:
            _params.update(kwargs)
        url = "https://api.sunrise-sunset.org/json"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, params=_params)
            r.raise_for_status()
        return r.json()

    def geohack_url_from_geo(self, geo: geopy.location.Location, name: Optional[str] = None) -> str:
        name = name.replace(' ', '_') if name else geo.raw['display_name'].replace(' ', '_')
        dn, mn, sn = self.dd2dms(geo.latitude)
        dw, mw, sw = self.dd2dms(geo.longitude)
        params = f"{dn}_{mn}_{sn}_N_{dw}_{mw}_{sw}_W_scale:500000"
        return f"https://geohack.toolforge.org/geohack.php?pagename={name}&params={params}"

    @staticmethod
    def dd2dms(dd: Union[float, int]) -> Tuple[int, int, int]:
        mult = -1 if dd < 0 else 1
        mnt, sec = divmod(abs(dd)*3600, 60)
        deg, mnt = divmod(mnt, 60)
        return abs(mult*deg), abs(mult*mnt), abs(mult*sec)

    # @commands.group(name='sunsetrise')
    # @commands.guild_only()
    # @commands.admin()
    # async def _sun(self, ctx: commands.Context):
    #     """Options for managing Basecog."""
    #
    # @_sun.command(name='location', aliases=['setlocation'])
    # @commands.max_concurrency(1, commands.BucketType.guild)
    # async def _sun_location(self, ctx: commands.Context):
    #     """Set Channels for Basecog"""
    #     pass
