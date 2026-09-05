from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from py_src.domain.value_objects.ad_metrics import AdMetrics
from py_src.domain.value_objects.ad_write_result import AdWriteResult
from py_src.infrastructure.api.ads_units_repository import AdsUnitsRepository
from py_src.infrastructure.sheets.ad_sales_sheet import AdSalesSheet
from py_src.usecases.update_ad_sales import EmptyAdsReportError, UpdateAdSalesUseCase

JST = timezone(timedelta(hours=9))


class TestUpdateAdSalesUseCase:
    def test_requests_the_last_14_days_ending_yesterday(self) -> None:
        ad_sheet = Mock(spec=AdSalesSheet)
        ad_sheet.write_ad_metrics.return_value = AdWriteResult(cells_written=0)
        ads_repository = Mock(spec=AdsUnitsRepository)
        ads_repository.get_daily_metrics.return_value = {
            "2026-06-02": {"B00EXAMPLE": AdMetrics(units=1)}
        }
        usecase = UpdateAdSalesUseCase(
            ad_sheet=ad_sheet, ads_repository=ads_repository, days=14,
        )

        usecase.execute()

        start, end = ads_repository.get_daily_metrics.call_args[0]
        yesterday = (datetime.now(JST) - timedelta(days=1)).date()
        assert end == yesterday
        assert start == yesterday - timedelta(days=13)

    def test_resolves_ad_rows_before_writing(self) -> None:
        ad_sheet = Mock(spec=AdSalesSheet)
        ad_sheet.write_ad_metrics.return_value = AdWriteResult(cells_written=5)
        ads_repository = Mock(spec=AdsUnitsRepository)
        ads_repository.get_daily_metrics.return_value = {
            "2026-06-02": {"B00EXAMPLE": AdMetrics(units=3)}
        }
        usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

        result = usecase.execute_range(date(2026, 6, 1), date(2026, 6, 3))

        ad_sheet.get_ad_rows.assert_called_once()
        ad_sheet.write_ad_metrics.assert_called_once_with({
            "2026-06-01": {},
            "2026-06-02": {"B00EXAMPLE": AdMetrics(units=3)},
            "2026-06-03": {},
        })
        assert result.cells_written == 5

    def test_report_failure_writes_nothing(self) -> None:
        ad_sheet = Mock(spec=AdSalesSheet)
        ads_repository = Mock(spec=AdsUnitsRepository)
        ads_repository.get_daily_metrics.side_effect = RuntimeError("レポート失敗")
        usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

        try:
            usecase.execute()
        except RuntimeError:
            pass

        ad_sheet.write_ad_metrics.assert_not_called()

    def test_backfill_range_overrides_the_default_window(self) -> None:
        ad_sheet = Mock(spec=AdSalesSheet)
        ad_sheet.write_ad_metrics.return_value = AdWriteResult(cells_written=0)
        ads_repository = Mock(spec=AdsUnitsRepository)
        ads_repository.get_daily_metrics.return_value = {
            "2026-06-15": {"B00EXAMPLE": AdMetrics(units=1)}
        }
        usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

        usecase.execute_range(date(2026, 6, 1), date(2026, 6, 30))

        assert ads_repository.get_daily_metrics.call_args[0] == (
            date(2026, 6, 1), date(2026, 6, 30),
        )

    def test_day_with_zero_units_but_a_present_row_still_reaches_the_sheet(self) -> None:
        # レポートが「その日・そのASINは0件」という行を返したケース。
        # metrics_by_date に実データ（値が0の行も含む）があれば空レポートとは扱わない。
        ad_sheet = Mock(spec=AdSalesSheet)
        ad_sheet.write_ad_metrics.return_value = AdWriteResult(cells_written=0)
        ads_repository = Mock(spec=AdsUnitsRepository)
        ads_repository.get_daily_metrics.return_value = {
            "2026-06-02": {"B00EXAMPLE": AdMetrics(units=0)}
        }
        usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

        usecase.execute_range(date(2026, 6, 1), date(2026, 6, 3))

        ad_sheet.write_ad_metrics.assert_called_once_with({
            "2026-06-01": {},
            "2026-06-02": {"B00EXAMPLE": AdMetrics(units=0)},
            "2026-06-03": {},
        })

    def test_empty_report_over_the_whole_range_raises_and_writes_nothing(self) -> None:
        ad_sheet = Mock(spec=AdSalesSheet)
        ads_repository = Mock(spec=AdsUnitsRepository)
        ads_repository.get_daily_metrics.return_value = {}
        usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

        with pytest.raises(EmptyAdsReportError):
            usecase.execute_range(date(2026, 6, 1), date(2026, 6, 14))

        ad_sheet.write_ad_metrics.assert_not_called()
