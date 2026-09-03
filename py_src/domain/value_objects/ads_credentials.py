from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

REGION_URLS = {
    "NA": "https://advertising-api.amazon.com",
    "EU": "https://advertising-api-eu.amazon.com",
    "FE": "https://advertising-api-fe.amazon.com",
}
REQUIRED_KEYS = (
    "AMAZON_CLIENT_ID",
    "AMAZON_CLIENT_SECRET",
    "AMAZON_REFRESH_TOKEN",
    "AMAZON_PROFILE_ID",
    "AMAZON_REGION",
)


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

    @classmethod
    def from_env_file(cls, path: Path) -> AdsCredentials:
        if not path.exists():
            raise FileNotFoundError(f"Ads API の資格情報が見つかりません: {path}")
        values = {k: v for k, v in dotenv_values(path).items() if v}
        missing = [key for key in REQUIRED_KEYS if key not in values]
        if missing:
            raise ValueError(f"{path} に足りないキー: {', '.join(missing)}")
        return cls(
            client_id=values["AMAZON_CLIENT_ID"],
            client_secret=values["AMAZON_CLIENT_SECRET"],
            refresh_token=values["AMAZON_REFRESH_TOKEN"],
            profile_id=values["AMAZON_PROFILE_ID"],
            region=values["AMAZON_REGION"],
        )
