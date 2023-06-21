import httpx
import os
from typing import Optional, Dict, List, Any


class GitHub(object):
    """
    :param access_token: GitHub Access Token or GITHUB_TOKEN environment variable
    """
    url = 'https://api.github.com'
    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.environ['GITHUB_TOKEN']
        self.headers = {
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Authorization': 'Bearer ' + self.access_token,
        }

    def __repr__(self):
        return f'GitHub(access_token=<{self.access_token[:6]}...>)'

    async def _get_request(self, url, params: Optional[dict] = None) -> Any:
        print(self.headers)
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, headers=self.headers, params=params)
            r.raise_for_status()
            return r.json()

    async def get_notifications(self, **params) -> List[dict]:
        """
        :param params: Query parameters for notifications endpoint
        :return: Dictionary from JSON response
        https://docs.github.com/en/rest/activity/notifications
        """
        url = f'{self.url}/notifications'
        return await self._get_request(url, params=params)

