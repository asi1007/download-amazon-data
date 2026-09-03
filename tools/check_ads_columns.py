from __future__ import annotations
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from py_src.infrastructure.api.ads_units_repository import AdsUnitsRepository
from py_src.infrastructure.api.ads_credentials_loader import load_ads_credentials

ADS_ENV = Path(__file__).resolve().parents[2] / "dwld-ad-data" / ".env"


def main() -> None:
    credentials = load_ads_credentials(ADS_ENV)
    repository = AdsUnitsRepository(credentials=credentials)
    target = date.today() - timedelta(days=2)
    units = repository.get_daily_units(target, target)
    print(f"{target} の行数: {sum(len(v) for v in units.values())}")
    for day, by_asin in units.items():
        for asin, count in sorted(by_asin.items(), key=lambda kv: -kv[1])[:10]:
            print(f"  {day} {asin} {count}")


if __name__ == "__main__":
    main()
