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
    metrics_by_date = repository.get_daily_metrics(target, target)
    print(f"{target} の行数: {sum(len(v) for v in metrics_by_date.values())}")
    for day, by_asin in metrics_by_date.items():
        ranked = sorted(by_asin.items(), key=lambda kv: -kv[1].units)[:10]
        for asin, metrics in ranked:
            print(f"  {day} {asin} 個数={metrics.units} 広告費={metrics.cost}")


if __name__ == "__main__":
    main()
