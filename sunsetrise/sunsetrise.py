import datetime
import discord
import httpx
import logging
import pytz
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from typing import Optional, Union, Tuple, Dict, List, Any

from redbot.core import app_commands, commands, Config

log = logging.getLogger('red.sunsetrise')


class Sunsetrise(commands.Cog):
    """Carl's Sunsetrise Cog"""

    user_default = {
        'location': None,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_user(**self.user_default)
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
        data = await self.get_sun_data(geo.latitude, geo.longitude)
        if data['status'] != 'OK':
            content = (f'⛔  Error getting Sun Data for: {location}\n'
                       f'Latitude: `{geo.latitude}` Longitude: `{geo.longitude}`')
            return await ctx.send(content)
        embed = discord.Embed(
            title=geo.raw['display_name'],
            timestamp=datetime.datetime.now(),
        )
        tz = self.tf.timezone_at(lat=geo.latitude, lng=geo.longitude)
        timezone = pytz.timezone(tz)
        sunrise_utc = datetime.datetime.fromisoformat(data['results']['sunrise'])
        sunrise = sunrise_utc.astimezone(timezone)
        embed.add_field(name='Sunrise', value=sunrise.strftime("%I:%M:%S %p"))
        sunset_utc = datetime.datetime.fromisoformat(data['results']['sunset'])
        sunset = sunset_utc.astimezone(timezone)
        embed.add_field(name='Sunset', value=sunset.strftime("%I:%M:%S %p"))
        duration = datetime.timedelta(seconds=int(data['results']['day_length']))
        embed.add_field(name='Day Length', value=str(duration))
        current_time_utc = datetime.datetime.now(pytz.UTC)
        current_time = current_time_utc.astimezone(timezone)
        if sunrise_utc < current_time < sunset_utc:
            embed.colour = discord.Colour.orange()
        else:
            embed.colour = discord.Colour.dark_blue()
        embed.set_author(name=f'Lat: {geo.latitude} Lon: {geo.longitude}')
        await ctx.send(embed=embed)

    @staticmethod
    async def get_sun_data(lat: Union[str, float],
                           lon: Union[str, float], **kwargs) -> Dict[str, Any]:
        _params = {'lat': lat, 'lng': lon, 'formatted': 0}
        if kwargs:
            _params.update(kwargs)
        url = f'https://api.sunrise-sunset.org/json'
        async with httpx.AsyncClient() as client:
            r = await client.get(url, params=_params)
            r.raise_for_status()
        return r.json()

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
