import datetime
import discord
import geopy
import httpx
import logging
import pytz
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from typing import Optional, Union, Tuple, Dict, List, Any

from redbot.core import app_commands, commands, Config

log = logging.getLogger('red.weather')


class Weather(commands.Cog):
    """Carl's Weather Cog"""

    url = 'https://forecast.weather.gov/MapClick.php?lon={lon}&lat={lat}'

    http_options = {
        'follow_redirects': True,
        'timeout': 10,
        'headers': {'user-agent': 'CarlBot'},
    }

    # user_default = {
    #     'location': None,
    # }

    def __init__(self, bot):
        self.bot = bot
        # self.config = Config.get_conf(self, 1337, True)
        # self.config.register_user(**self.user_default)
        self.gl = Nominatim(user_agent=self.__cog_name__)
        self.tf = TimezoneFinder()

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.hybrid_command(name='weather', aliases=['noaa'],
                             description='Get Weather for <location>')
    @commands.guild_only()
    @app_commands.describe(location='Location to get Weather for')
    async def weather_command(self, ctx: commands.Context, *, location: str):
        """Get Weather for <location>"""
        async with ctx.typing():
            try:
                geo = self.gl.geocode(location)
                if not geo or not geo.latitude or not geo.longitude:
                    return await ctx.send(f'⛔  Error getting Lat/Lon Data for: {location}')
                weather, forecast = await self.get_weather(geo.latitude, geo.longitude)
                if not weather or not weather['features']:
                    return await ctx.send(f'⛔  Error getting Weather for: {location}\n'
                                          f'Lat: `{geo.latitude}` Lon: `{geo.longitude}`')
                # tz = self.tf.timezone_at(lat=geo.latitude, lng=geo.longitude)
                # timezone = pytz.timezone(tz)
                # current_time_utc = datetime.datetime.now(pytz.UTC)
                # current_time = current_time_utc.astimezone(timezone)
                embed = self.gen_embed(geo, weather['features'][0]['properties'],
                                       forecast['properties']['periods'][0])
                await ctx.send(embed=embed)
            except Exception as error:
                log.exception(error)
                content = (f'Error fetching Weather, please try again '
                           f'or wait until later.\nError: `{error}`')
                await ctx.send(content=content)

    def gen_embed(self, geo: geopy.location.Location, weather: Dict[str, Any],
                  period: Dict[str, Any]) -> discord.Embed:
        embed = discord.Embed(
            title=geo.raw['display_name'],
            url=self.url.format(lat=geo.latitude, lon=geo.longitude),
            timestamp=datetime.datetime.now(),
        )
        embed.set_author(
            name=f'Lat: {geo.latitude} / Lon: {geo.longitude}',
            url=self.geohack_url_from_geo(geo),
        )
        if weather['icon']:
            embed.set_thumbnail(url=weather['icon'])

        description = ''
        if weather['textDescription']:
            description += f"Currently {weather['textDescription']}. "
        description += f"{period['name']}"
        if period['detailedForecast']:
            description += f", {period['detailedForecast']}"
        embed.description = description

        if weather['temperature']['value']:
            temp = self._num((weather['temperature']['value'] * 9/5) + 32, to=1)
            temp_s = temp + ' °F'
        else:
            temp = None
            temp_s = 'N/A'
        embed.add_field(name='Temperature', value=f"{temp_s}")

        if weather['dewpoint']['value']:
            dew = self._num((weather['dewpoint']['value'] * 9/5) + 32, to=1, suffix=' °F')
        else:
            dew = 'N/A'
        embed.add_field(name='Dew Point', value=f"{dew}")

        if weather['relativeHumidity']['value']:
            humi = self._num(weather['relativeHumidity']['value'], to=1, suffix=' %')
        else:
            humi = 'N/A'
        embed.add_field(name='Humidity', value=f"{humi}")

        if weather['windSpeed']['value']:
            speed = self._num(weather['windSpeed']['value'] / 1.609344, to=1, suffix=' mph')
        else:
            speed = 'N/A'
        embed.add_field(name='Wind Speed', value=f"{speed}")

        if weather['windGust']['value']:
            gust = self._num(weather['windGust']['value'] / 1.609344, to=1, suffix=' mph')
        else:
            gust = 'N/A'
        embed.add_field(name='Wind Gust', value=f"{gust}")

        direction = str(weather['windDirection']['value']) or 'N/A'
        direction += '°' if weather['windDirection']['value'] else ''
        embed.add_field(name='Wind Direction', value=f"{direction}")

        if weather['barometricPressure']['value']:
            pressure = format(weather['barometricPressure']['value'] / 3386.39, '.2f')
            embed.add_field(name='Pressure', value=f"{pressure} inHg")

        if weather['elevation']['value']:
            elevation = self._num(weather['elevation']['value'] * 3.28084, suffix=' ft')
            embed.add_field(name='Elevation', value=f"{elevation}")

        tz = self.tf.timezone_at(lat=geo.latitude, lng=geo.longitude)
        embed.add_field(name='Time Zone', value=f"{tz}")

        if temp:
            temp_f = float(temp)
            if temp_f < 0:
                embed.colour = discord.Colour.purple()
            elif 0 <= temp_f < 32:
                embed.colour = discord.Colour.blue()
            elif 32 <= temp_f < 65:
                embed.colour = discord.Colour.dark_teal()
            elif 65 <= temp_f < 75:
                embed.colour = discord.Colour.green()
            elif 75 <= temp_f < 85:
                embed.colour = discord.Colour.yellow()
            elif 85 <= temp_f < 95:
                embed.colour = discord.Colour.orange()
            elif 95 <= temp_f:
                embed.colour = discord.Colour.red()
        else:
            embed.colour = discord.Colour.light_gray()
        return embed

    async def get_weather(self, lat: float, lon: float) -> Tuple[dict, dict]:
        location_url = f'https://api.weather.gov/points/{lat},{lon}'
        location_data: Dict[str, Any] = await self._get_json(location_url)

        forecast_url: str = location_data["properties"]["forecast"]
        forecast: Dict[str, Any] = await self._get_json(forecast_url)

        stations_url: str = location_data["properties"]["observationStations"]
        stations: Dict[str, Any] = await self._get_json(stations_url)

        # dt = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S+00:00')
        observation_url: str = stations["features"][0]["id"] + f'/observations'
        observation: Dict[str, Any] = await self._get_json(observation_url)

        return observation, forecast

    async def _get_json(self, url: str, **kwargs) -> Dict[str, Any]:
        log.debug('url: %s', url)
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, params=kwargs)
            r.raise_for_status()
        return r.json()

    def geohack_url_from_geo(self, geo: geopy.location.Location, name: Optional[str] = None) -> str:
        name = name.replace(' ', '_') if name else geo.raw['display_name'].replace(' ', '_')
        dn, mn, sn = self.dd2dms(geo.latitude)
        dw, mw, sw = self.dd2dms(geo.longitude)
        params = f'{dn}_{mn}_{sn}_N_{dw}_{mw}_{sw}_W_scale:500000'
        return f'https://geohack.toolforge.org/geohack.php?pagename={name}&params={params}'

    @staticmethod
    def dd2dms(dd: Union[float, int]) -> Tuple[int, int, int]:
        """DD to DMS"""
        mult = -1 if dd < 0 else 1
        mnt, sec = divmod(abs(dd)*3600, 60)
        deg, mnt = divmod(mnt, 60)
        return abs(mult*deg), abs(mult*mnt), abs(mult*sec)

    @staticmethod
    def _num(number: Union[float, int], to: Optional[int] = 0,
             prefix: Optional[str] = '', suffix: Optional[str] = '') -> str:
        """Remove Trailing Zeros and Decimal with Prefix and Suffix"""
        digit = str(round(number, to)).rstrip('0').rstrip('.')
        return prefix + digit + suffix

    # async def get_forecast(self, lat: float, lon: float) -> Dict[str, Any]:
    #     location_url = f'https://api.weather.gov/points/{lat},{lon}'
    #     location_data: Dict[str, Any] = await self._get_json(location_url)
    #
    #     forecast_url: str = location_data["properties"]["forecast"]
    #     forecast: Dict[str, Any] = await self._get_json(forecast_url)
    #
    #     return forecast
    #
    # def gen_forecast_embed(self, geo: geopy.location.Location, period: Dict[str, Any]) -> discord.Embed:
    #     embed = discord.Embed(
    #         title=geo.raw['display_name'],
    #         url=self.url.format(lat=geo.latitude, lon=geo.longitude),
    #         description=period['detailedForecast'],
    #     )
    #     embed.set_author(name=period['name'])
    #     embed.set_thumbnail(url=period['icon'])
    #     trend = period['temperatureTrend']  # TODO: Add Trends - None, "falling", UNKNOWN
    #     temp = f"{period['temperature']} {period['temperatureUnit']}"
    #     dew_f = (period['dewpoint']['value'] * 9/5) + 32
    #     embed.add_field(name='Temperature', value=temp)
    #     embed.add_field(name='Humidity', value=f"{period['relativeHumidity']['value']}%")
    #     embed.add_field(name='Dew Point', value=f"{dew_f} F")
    #     embed.add_field(name='Wind Speed', value=f"{period['windSpeed']}")
    #     embed.add_field(name='Wind Direction', value=f"{period['windDirection']}")
    #     return embed
