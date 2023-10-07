import os
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class FlightAware(object):
    """
    :param api_key: FlightAware API Key or AEROAPI_KEY environment variable
    """
    fa_id_url = 'https://flightaware.com/live/flight/id/'
    fa_flight_url = 'https://flightaware.com/live/flight/'
    fa_aircraft_url = 'https://flightaware.com/live/aircrafttype/'
    fa_fleet_url = 'https://flightaware.com/live/fleet/'
    fa_airport_url = 'https://flightaware.com/resources/airport/'
    fa_registration_url = 'https://flightaware.com/resources/registration/'
    fr24_reg_url = 'https://www.flightradar24.com/data/aircraft/'
    airfleets_search_url = 'https://www.airfleets.net/recherche/?key='
    jetphotos_url = 'https://www.jetphotos.com/registration/'
    liveatc_url = 'https://www.liveatc.net/search/?icao='
    airnav_url = 'https://www.airnav.com/airport/'

    url = 'https://aeroapi.flightaware.com/aeroapi'
    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ['AEROAPI_KEY']
        self.headers = {
            'Accept': 'application/json; charset=UTF-8',
            'x-apikey': self.api_key,
        }

    def __repr__(self):
        return f'FlightAware(api_key=<{self.api_key[:6]}...>)'

    async def _get_request(self, url, **kwargs) -> Dict[str, Any]:
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, headers=self.headers, **kwargs)
            r.raise_for_status()
            return r.json()

    async def flights_ident(self, ident: str,
                            params: Optional[Dict[str, Any]] = None
                            ) -> Dict[str, Any]:
        """
        :param ident: Registration, Flight Number, FA ID
        :param params: Optional: Additional query parameters
        :return: Dictionary from JSON response
        """
        start = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        data = {'start': start}
        url = f'{self.url}/flights/{ident.upper()}'
        params = params.update(data) if params else data
        return await self._get_request(url, params=params)

    async def flights_search(self, query: str) -> Dict[str, Any]:
        """
        :param query: FA Search Query String
        :return: Dictionary from JSON response
        """
        url = f'{self.url}/flights/search'
        params = {'query': query}
        return await self._get_request(url, params=params)

    async def flights_map(self, fa_id: str) -> Dict[str, Any]:
        """
        :param fa_id: FlightAware Flight ID
        :return: Dictionary from JSON response
        """
        url = f'{self.url}/flights/{fa_id}/map'
        return await self._get_request(url)

    async def operators_id(self, operator_id: str) -> Dict[str, Any]:
        """
        :param operator_id: Operator ICAO or IATA ID
        :return: Dictionary from JSON response
        """
        url = f'{self.url}/operators/{operator_id}'
        return await self._get_request(url)

    async def owner_ident(self, ident: str) -> Dict[str, Any]:
        """
        :param ident: Registration, Flight Number
        :return: Dictionary from JSON response
        """
        url = f'{self.url}/aircraft/{ident.upper()}/owner'
        return await self._get_request(url)
