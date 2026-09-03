from __future__ import annotations
from datetime import date, datetime, timedelta, timezone

from py_src.domain.value_objects.ad_write_result import AdWriteResult

JST = timezone(timedelta(hours=9))
DEFAULT_DAYS = 14


class EmptyAdsReportError(RuntimeError):
    pass


class UpdateAdSalesUseCase:
    def __init__(
        self, ad_sheet: object, ads_repository: object, days: int = DEFAULT_DAYS,
    ) -> None:
        self._ad_sheet = ad_sheet
        self._ads_repository = ads_repository
        self._days = days

    def execute(self) -> AdWriteResult:
        end = (datetime.now(JST) - timedelta(days=1)).date()
        start = end - timedelta(days=self._days - 1)
        return self.execute_range(start, end)

    def execute_range(self, start: date, end: date) -> AdWriteResult:
        self._ad_sheet.get_ad_rows()
        units_by_date = self._ads_repository.get_daily_units(start, end)
        self._guard_against_empty_report(units_by_date, start, end)
        filled_units_by_date = self._fill_missing_dates(units_by_date, start, end)
        return self._ad_sheet.write_ad_units(filled_units_by_date)

    @staticmethod
    def _guard_against_empty_report(
        units_by_date: dict[str, dict[str, int]], start: date, end: date,
    ) -> None:
        if not any(units_by_date.values()):
            raise EmptyAdsReportError(
                f"広告レポートが {start}〜{end} で1行も返しませんでした"
                "（認証切れ・プロファイルID誤り・Amazon側障害の可能性）"
            )

    @staticmethod
    def _fill_missing_dates(
        units_by_date: dict[str, dict[str, int]], start: date, end: date,
    ) -> dict[str, dict[str, int]]:
        days_in_range = (end - start).days + 1
        all_days = (start + timedelta(days=offset) for offset in range(days_in_range))
        return {day.isoformat(): units_by_date.get(day.isoformat(), {}) for day in all_days}
