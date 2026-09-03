from dataclasses import dataclass

REGION_URLS = {
    "NA": "https://advertising-api.amazon.com",
    "EU": "https://advertising-api-eu.amazon.com",
    "FE": "https://advertising-api-fe.amazon.com",
}


@dataclass(frozen=True)
class AdsCredentials:
    client_id: str
    client_secret: str
    refresh_token: str
    profile_id: str
    region: str

    @property
    def api_base_url(self) -> str:
        return REGION_URLS[self.region]
