from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock

from py_src.usecases.update_ad_sales import UpdateAdSalesUseCase

JST = timezone(timedelta(hours=9))


class TestUpdateAdSalesUseCase:
    def test_requests_the_last_14_days_ending_yesterday(self) -> None:
        ad_sheet = Mock()
        ad_sheet.write_ad_units.return_value = 0
        ads_repository = Mock()
        ads_repository.get_daily_units.return_value = {}
        usecase = UpdateAdSalesUseCase(
            ad_sheet=ad_sheet, ads_repository=ads_repository, days=14,
        )

        usecase.execute()

        start, end = ads_repository.get_daily_units.call_args[0]
        yesterday = (datetime.now(JST) - timedelta(days=1)).date()
        assert end == yesterday
        assert start == yesterday - timedelta(days=13)

    def test_resolves_ad_rows_before_writing(self) -> None:
        ad_sheet = Mock()
        ad_sheet.write_ad_units.return_value = 5
        ads_repository = Mock()
        ads_repository.get_daily_units.return_value = {"2026-06-02": {"B00EXAMPLE": 3}}
        usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

        written = usecase.execute_range(date(2026, 6, 1), date(2026, 6, 3))

        ad_sheet.get_ad_rows.assert_called_once()
        ad_sheet.write_ad_units.assert_called_once_with({
            "2026-06-01": {},
            "2026-06-02": {"B00EXAMPLE": 3},
            "2026-06-03": {},
        })
        assert written == 5

    def test_report_failure_writes_nothing(self) -> None:
        ad_sheet = Mock()
        ads_repository = Mock()
        ads_repository.get_daily_units.side_effect = RuntimeError("レポート失敗")
        usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

        try:
            usecase.execute()
        except RuntimeError:
            pass

        ad_sheet.write_ad_units.assert_not_called()

    def test_backfill_range_overrides_the_default_window(self) -> None:
        ad_sheet = Mock()
        ad_sheet.write_ad_units.return_value = 0
        ads_repository = Mock()
        ads_repository.get_daily_units.return_value = {}
        usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

        usecase.execute_range(date(2026, 6, 1), date(2026, 6, 30))

        assert ads_repository.get_daily_units.call_args[0] == (
            date(2026, 6, 1), date(2026, 6, 30),
        )

    def test_single_day_with_no_ad_sales_still_reaches_the_sheet(self) -> None:
        ad_sheet = Mock()
        ad_sheet.write_ad_units.return_value = 0
        ads_repository = Mock()
        ads_repository.get_daily_units.return_value = {}
        usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

        usecase.execute_range(date(2026, 6, 1), date(2026, 6, 1))

        ad_sheet.write_ad_units.assert_called_once_with({"2026-06-01": {}})
