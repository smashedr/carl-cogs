import httpx
import os
from typing import Optional, List, Any


class GitHub(object):
    """
    :param access_token: GitHub Access Token or GITHUB_TOKEN environment variable
    """
    api_version = '2022-11-28'
    url = 'https://api.github.com'

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.environ['GITHUB_TOKEN']
        self.headers = {
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': self.api_version,
            'Authorization': 'Bearer ' + self.access_token,
        }
        self.http_options = {
            'follow_redirects': True,
            'timeout': 10,
            'headers': self.headers,
        }

    def __repr__(self):
        return f'GitHub(access_token=<{self.access_token[:6]}...>)'

    async def _get_json(self, url, params: Optional[dict] = None) -> Any:
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()

    async def get_notifications(self, **params) -> List[dict]:
        """
        :param params: Query parameters for notifications endpoint
        :return: Dictionary from JSON response
        https://docs.github.com/en/rest/activity/notifications
        """
        url = f'{self.url}/notifications'
        return await self._get_json(url, params=params)

