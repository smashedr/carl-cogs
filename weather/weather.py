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
        geo = self.gl.geocode(location)
        if not geo or not geo.latitude or not geo.longitude:
            return await ctx.send(f'⛔  Error getting Lat/Lon Data for: {location}')
        weather: Dict[str, Any] = await self.get_weather(geo.latitude, geo.longitude)
        if not weather or not weather['features']:
            return await ctx.send(f'⛔  Error getting Weather for: {location}\n'
                                  f'Lat: `{geo.latitude}` Lon: `{geo.longitude}`')
        log.debug('-'*40)
        log.debug(weather)
        log.debug('-'*40)
        # tz = self.tf.timezone_at(lat=geo.latitude, lng=geo.longitude)
        # timezone = pytz.timezone(tz)
        # current_time_utc = datetime.datetime.now(pytz.UTC)
        # current_time = current_time_utc.astimezone(timezone)
        embed = self.gen_embed(geo, weather['features'][0]['properties'])
        await ctx.send(embed=embed)

    def gen_embed(self, geo: geopy.location.Location, weather: Dict[str, Any]) -> discord.Embed:
        embed = discord.Embed(
            title=geo.raw['display_name'],
            url=self.url.format(lat=geo.latitude, lon=geo.longitude),
            description=weather['textDescription'] or None,
            timestamp=datetime.datetime.now(),
        )
        embed.set_author(name=f'Lat: {geo.latitude} / Lon: {geo.longitude}')
        if weather['icon']:
            embed.set_thumbnail(url=weather['icon'])

        if weather['temperature']['value']:
            temp = round((weather['temperature']['value'] * 9/5) + 32, 1)
        else:
            temp = 'Unknown'
        embed.add_field(name='Temperature', value=f"{temp} F")

        if weather['dewpoint']['value']:
            dew = round((weather['dewpoint']['value'] * 9/5) + 32, 1)
        else:
            dew = 'Unknown'
        embed.add_field(name='Dew Point', value=f"{dew} F")

        if weather['relativeHumidity']['value']:
            humi = round(weather['relativeHumidity']['value'], 1)
        else:
            humi = 'Unknown'
        embed.add_field(name='Humidity', value=f"{humi} %")

        speed = weather['windSpeed']['value'] or 0
        embed.add_field(name='Wind Speed', value=f"{speed} km/h")
        gust = weather['windGust']['value'] or 0
        embed.add_field(name='Wind Gust', value=f"{gust} km/h")
        direction = weather['windDirection']['value'] or 'Still'
        embed.add_field(name='Wind Direction', value=f"{direction}")

        if weather['elevation']['value']:
            elevation = round(weather['elevation']['value'] * 3.28084, 1)
            embed.add_field(name='Elevation', value=f"{elevation} Ft")

        if weather['barometricPressure']['value']:
            pressure = weather['barometricPressure']['value']
            embed.add_field(name='Pressure', value=f"{pressure} Pa")

        tz = self.tf.timezone_at(lat=geo.latitude, lng=geo.longitude)
        embed.add_field(name='Time Zone', value=f"{tz}")
        return embed

    async def get_weather(self, lat: float, lon: float) -> Dict[str, Any]:
        location_url = f'https://api.weather.gov/points/{lat},{lon}'
        location_data: Dict[str, Any] = await self._get_json(location_url)

        # forecast_url: str = location_data["properties"]["forecast"]
        # forecast: Dict[str, Any] = await self._get_json(forecast_url)

        stations_url: str = location_data["properties"]["observationStations"]
        stations: Dict[str, Any] = await self._get_json(stations_url)

        # dt = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S+00:00')
        observation_url: str = stations["features"][0]["id"] + f'/observations'
        observation: Dict[str, Any] = await self._get_json(observation_url)

        return observation

    async def get_forecast(self, lat: float, lon: float) -> Dict[str, Any]:
        location_url = f'https://api.weather.gov/points/{lat},{lon}'
        location_data: Dict[str, Any] = await self._get_json(location_url)

        forecast_url: str = location_data["properties"]["forecast"]
        forecast: Dict[str, Any] = await self._get_json(forecast_url)

        return forecast

    async def _get_json(self, url: str, **kwargs) -> Dict[str, Any]:
        log.debug('url: %s', url)
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, params=kwargs)
            r.raise_for_status()
        return r.json()

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
