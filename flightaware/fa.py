import os
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class FlightAware(object):
    """
    :param api_key: FlightAware API Key or AEROAPI_KEY environment variable
    """
    fa_flight_url = 'https://flightaware.com/live/flight/'
    fa_airport_url = 'https://flightaware.com/live/airport/'
    fa_aircraft_url = 'https://flightaware.com/live/aircrafttype/'
    fa_registration_url = 'https://flightaware.com/resources/registration/'
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
        # self.client = httpx.AsyncClient(**self.http_options)
        # self.client.headers.update(self.headers)
        # self.fa_flight_id: Optional[str] = None

    def __repr__(self):
        return f'FlightAware(api_key=<{self.api_key[:6]}...>)'

    def get_client(self) -> httpx.AsyncClient:
        client = httpx.AsyncClient(**self.http_options)
        client.headers.update(self.headers)
        return client

    async def flights_search(self, query: str) -> Dict[str, Any]:
        """
        :param query: FA Search Query String
        :return: Dictionary from JSON response
        """
        url = f'{self.url}/flights/search'
        p = {'query': query}
        async with self.get_client() as client:
            r = await client.get(url, params=p)
            if not r.is_success:
                r.raise_for_status()
            return r.json()

    # async def flights_search_ident(self, ident: str):
    #     data = await self.flights_search(f'-idents "{ident}"')
    #     if data['flights']:
    #         self.fa_flight_id = data[0]['fa_flight_id']
    #     return data

    async def flights_ident(
            self, ident: str,
            params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        :param ident: Registration, Flight Number, FA ID
        :param params: Additional query parameters
        :return: Dictionary from JSON response
        """
        url = f'{self.url}/flights/{ident.upper()}'
        now = datetime.now()
        p = {
            'start': (now - timedelta(days=3)).strftime('%Y-%m-%d'),
        }
        p.update(params or {})
        async with self.get_client() as client:
            r = await client.get(url, params=p)
            if not r.is_success:
                r.raise_for_status()
            return r.json()

    async def flights_map(self, fa_id: str) -> Optional[Dict[str, Any]]:
        """
        :param fa_id: FlightAware Flight ID
        :return: Dictionary from JSON response
        """
        url = f'{self.url}/flights/{fa_id}/map'
        async with self.get_client() as client:
            r = await client.get(url)
            if not r.is_success:
                r.raise_for_status()
            return r.json()

    async def operators_id(self, operator_id: str) -> Optional[Dict[str, Any]]:
        """
        :param operator_id: Operator ICAO or IATA ID
        :return: Dictionary from JSON response
        """
        url = f'{self.url}/operators/{operator_id}'
        print(url)
        async with self.get_client() as client:
            r = await client.get(url)
            if not r.is_success:
                r.raise_for_status()
            return r.json()

    async def owner_ident(self, ident: str) -> Dict[str, Any]:
        """
        :param ident: Registration, Flight Number
        :return: Dictionary from JSON response
        """
        url = f'{self.url}/aircraft/{ident.upper()}/owner'
        async with self.get_client() as client:
            r = await client.get(url)
            if not r.is_success:
                r.raise_for_status()
            return r.json()


async def main():
    fa = FlightAware('NKvlLrgaLaXDf4bVLW4ex9OwCf782Aoa')
    # j = await fa.flights_ident('SKW132C')
    # j = await fa.owner_ident('N954AK')
    j = await fa.flights_map('AAL710-1684692012-airline-2240p')
    pprint(j)


if __name__ == '__main__':
    import asyncio
    from pprint import pprint
    asyncio.run(main())
