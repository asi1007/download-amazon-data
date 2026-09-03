from __future__ import annotations
import sys
from datetime import date, datetime, timedelta

from main import ADS_ENV_PATH, _open_spreadsheet
from py_src.infrastructure.api.ads_credentials_loader import load_ads_credentials
from py_src.infrastructure.api.ads_units_repository import AdsUnitsRepository
from py_src.infrastructure.sheets.ad_sales_sheet import AdSalesSheet
from py_src.usecases.update_ad_sales import UpdateAdSalesUseCase

MAX_DAYS_PER_REPORT = 31


def split_into_chunks(
    start: date, end: date, max_days: int = MAX_DAYS_PER_REPORT
) -> list[tuple[date, date]]:
    if start > end:
        raise ValueError(f"開始日が終了日より後です: {start} > {end}")
    chunks: list[tuple[date, date]] = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=max_days - 1), end)
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)
    return chunks


def main() -> None:
    if len(sys.argv) < 3:
        print("使い方: backfill_ad_sales.py <開始日 YYYY-MM-DD> <終了日 YYYY-MM-DD>")
        sys.exit(1)
    start = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    end = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()

    credentials = load_ads_credentials(ADS_ENV_PATH)
    ads_repository = AdsUnitsRepository(credentials=credentials)
    spreadsheet = _open_spreadsheet()
    ad_sheet = AdSalesSheet(worksheet=spreadsheet.worksheet("売上/日"))
    usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

    total = 0
    for chunk_start, chunk_end in split_into_chunks(start, end):
        written = usecase.execute_range(chunk_start, chunk_end)
        print(f"{chunk_start} 〜 {chunk_end}: {written} セル")
        total += written
    print(f"合計 {total} セル書き込みました")


if __name__ == "__main__":
    main()
