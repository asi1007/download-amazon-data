from pathlib import Path

from amazon_api import ads_credentials
from dotenv import dotenv_values

from py_src.domain.value_objects.ads_credentials import AdsCredentials

REQUIRED_KEYS = ("AMAZON_PROFILE_ID", "AMAZON_REGION")


def load_ads_credentials(path: Path) -> AdsCredentials:
    if not path.exists():
        raise FileNotFoundError(f"Ads API の資格情報が見つかりません: {path}")
    values = {k: v for k, v in dotenv_values(path).items() if v}
    missing = [key for key in REQUIRED_KEYS if key not in values]
    if missing:
        raise ValueError(f"{path} に足りないキー: {', '.join(missing)}")
    shared = ads_credentials()
    return AdsCredentials(
        client_id=shared.client_id,
        client_secret=shared.client_secret,
        refresh_token=shared.refresh_token,
        profile_id=values["AMAZON_PROFILE_ID"],
        region=values["AMAZON_REGION"],
    )
