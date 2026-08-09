from __future__ import annotations
import time
import requests

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
SP_API_BASE = "https://sellingpartnerapi-fe.amazon.com"


class SpApiAuthenticator:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        session: requests.Session | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._session = session or requests.Session()
        self._access_token: str | None = None

    def authenticate(self) -> None:
        response = self._session.post(LWA_TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        })
        response.raise_for_status()
        self._access_token = response.json()["access_token"]

    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-amz-access-token": self._access_token or "",
        }

    def request(self, method: str, url: str, max_retries: int = 5) -> requests.Response:
        connection_error: requests.exceptions.RequestException | None = None
        for attempt in range(max_retries):
            time.sleep(2 if attempt == 0 else 10)
            try:
                response = self._session.request(method, url, headers=self.headers())
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
                connection_error = error
                continue
            connection_error = None
            if response.status_code == 429:
                continue
            if response.status_code == 403:
                self.authenticate()
                continue
            response.raise_for_status()
            return response
        if connection_error is not None:
            raise connection_error
        response.raise_for_status()
        return response
