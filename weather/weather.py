import datetime
import discord
import geopy
import httpx
import logging
import xmltodict
from geopy.geocoders import Nominatim
from metar import Metar
from timezonefinder import TimezoneFinder
from typing import Any, Dict, List, Optional, Tuple, Union

from redbot.core import app_commands, commands
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.weather')


class Weather(commands.Cog):
    """Carl's Weather Cog"""

    url = 'https://forecast.weather.gov/MapClick.php?lon={lon}&lat={lat}'
    metar = 'https://www.aviationweather.gov/metar/data?ids={loc}&format=raw&hours={hours}&taf=off&layout=on'

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

    @commands.hybrid_command(name='weather', aliases=['noaa'], description='Get Weather for <location>')
    @commands.guild_only()
    @app_commands.describe(location='Location to get Weather for')
    async def weather_command(self, ctx: commands.Context, *, location: str):
        """Get Weather for <location>"""
        location = location.strip('` ')
        async with ctx.typing():
            try:
                geo = self.gl.geocode(location)
                if not geo or not geo.latitude or not geo.longitude:
                    content = f'⛔ Error getting Lat/Lon Data for: {location}'
                    return await ctx.send(content, delete_after=30)
                weather, forecast = await self.get_weather(geo.latitude, geo.longitude)
                log.debug('-'*40)
                log.debug(weather)
                log.debug('-'*40)
                if not weather or not weather['properties']:
                    content = (f'⛔ Error getting Weather for: {location}\n'
                               f'Lat: `{geo.latitude}` Lon: `{geo.longitude}`')
                    return await ctx.send(content, delete_after=30)
                # tz = self.tf.timezone_at(lat=geo.latitude, lng=geo.longitude)
                # timezone = pytz.timezone(tz)
                # current_time_utc = datetime.datetime.now(pytz.UTC)
                # current_time = current_time_utc.astimezone(timezone)
                content = f"`{weather['properties']['rawMessage']}`"
                embed = self.gen_embed(geo, weather['properties'], forecast['properties']['periods'][0])
                await ctx.send(content=content, embed=embed)
            except Exception as error:
                log.exception(error)
                content = (f'⛔ Error fetching Weather, please try again '
                           f'or wait until later.\nError: `{error}`')
                await ctx.send(content=content, delete_after=30)

    def gen_embed(self, geo: geopy.location.Location, weather: Dict[str, Any],
                  period: Dict[str, Any]) -> discord.Embed:

        embed = discord.Embed(
            title=geo.raw['display_name'],
            url=self.url.format(lat=geo.latitude, lon=geo.longitude),
            timestamp=datetime.datetime.fromisoformat(weather['timestamp']),
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
        if period['detailedForecast']:
            description += f"{period['name']}, {period['detailedForecast']}"
        embed.description = description.strip()

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

        observation_url: str = stations["features"][0]["id"] + '/observations/latest'
        observation: Dict[str, Any] = await self._get_json(observation_url)

        return observation, forecast

    @commands.hybrid_command(name='metar', aliases=['metars'], description='Decode <metar>')
    @commands.guild_only()
    @app_commands.describe(metar='METAR to Decode')
    async def metar_command(self, ctx: commands.Context, *, metar: str):
        """Decode <metar>"""
        await ctx.typing()
        metar = metar.upper().replace('METAR', '').strip('`()[]{}:;"\' ')
        try:
            obs = Metar.Metar(metar)
            url = self.metar.format(loc=obs.station_id, hours=0)
            await ctx.send(f'METAR for **{obs.station_id}** at `{obs.time}`\n<{url}>\n{obs.string()}')
        except Exception as error:
            log.error(error)
            await ctx.send(f'⛔ Error: {error}', delete_after=30)

    @commands.hybrid_command(name='getmetar', aliases=['getmetars'], description='Get METAR for <location>')
    @commands.guild_only()
    @app_commands.describe(station='Station to get METAR for', hours='Hours of METARS to fetch')
    async def getmetar_command(self, ctx: commands.Context, station: str, hours: Optional[int] = 1):
        """Get METAR for <station>"""
        await ctx.typing()
        station = station.upper().strip('` ')
        log.debug('station: %s', station)
        log.debug('hours: %s', hours)
        if hours < 1:
            return await ctx.send(f'⛔ Hours must be 1 or greater.', delete_after=30)

        metars = await self.get_metar(station, hours)
        if not metars:
            return await ctx.send(f'⛔ No Results for: {station}', delete_after=30)

        url = self.metar.format(loc=station, hours=hours)
        if len(metars) == 1:
            obs = Metar.Metar(metars[0]['raw_text'])
            content = f'METAR for **{obs.station_id}** at `{obs.time}`\n<{url}>\n{obs.string()}'
            return await ctx.send(content)

        metas = [x['raw_text'] for x in metars]
        plain = cf.box('\n'.join(metas))
        log.debug('metas: %s', metas)
        content = f'METARS `{len(metars)}` for **{station}** over `{hours}` hours:\n<{url}>\n{plain}'
        await ctx.send(content)

    async def get_metar(self, location: str, hours: Optional[int] = 1) -> Optional[List[dict]]:
        url = 'https://www.aviationweather.gov/adds/dataserver_current/httpparam'
        params = {
            'dataSource': 'metars',
            'requestType': 'retrieve',
            'format': 'xml',
            'stationString': location,
            'hoursBeforeNow': hours,
        }
        r = await self._get_json(url, json=False, **params)
        log.debug('r.url: %s', r.url)
        # log.debug('r.text: %s', r.text)
        data = xmltodict.parse(r.text)['response']['data']
        if int(data['@num_results']) < 1:
            return
        elif int(data['@num_results']) == 1:
            return [data['METAR']]
        else:
            return data['METAR']

    async def _get_json(self, url: str, json=True, **kwargs) -> Union[Dict[str, Any], httpx.Response]:
        log.debug('url: %s', url)
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, params=kwargs)
            r.raise_for_status()
        if json:
            return r.json()
        else:
            return r

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
