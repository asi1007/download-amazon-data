from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from py_src.domain.value_objects.actual_profit_cell import ActualProfitWriteResult
from py_src.domain.value_objects.finance_record import FinanceRecord
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.unit_costs import UnitCosts
from py_src.infrastructure.api.finances_repository import FinancesRepository
from py_src.infrastructure.api.orders_report_repository import OrdersReportRepository
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository
from py_src.infrastructure.sheets.fee_gap_sheet import FeeGapSheet
from py_src.infrastructure.sheets.product_index_reader import ProductIndex, ProductIndexReader
from py_src.infrastructure.sheets.sales_sheet import SalesSheet
from py_src.usecases.update_actual_gross_profit import (
    EmptyFinancesResultError,
    UpdateActualGrossProfitUseCase,
)

JST = timezone(timedelta(hours=9))


def _parse_utc(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
ORDER_DATE = date(2026, 9, 1)
INDEX = ProductIndex(
    costs={"B00EXAMPLE": UnitCosts(selling_fee=100.0, fba_fee=200.0, cost=400.0)},
    names={"B00EXAMPLE": "ルーペ"},
    sku_to_asin={"SKU-A": "B00EXAMPLE"},
)


def _build(records: list[FinanceRecord] | None = None) -> tuple:
    sheet = Mock(spec=SalesSheet)
    sheet.get_asin_list.return_value = ["B00EXAMPLE"]
    sheet.write_actual_gross_profit.return_value = ActualProfitWriteResult(cells_written=1)
    sales_repo = Mock(spec=SpApiSalesRepository)
    sales_repo.get_sales_by_date.return_value = {
        "B00EXAMPLE": {ORDER_DATE: SalesInfo(unit_count=3, total_sales_amount=6000.0)}
    }
    orders_repo = Mock(spec=OrdersReportRepository)
    orders_repo.get_purchase_dates.return_value = {"503-1": ORDER_DATE}
    finances_repo = Mock(spec=FinancesRepository)
    finances_repo.get_finance_records.return_value = (
        records
        if records is not None
        else [FinanceRecord("503-1", "SKU-A", quantity=3, fba_fee_amount=756.0, referral_fee_amount=294.0)]
    )
    index_reader = Mock(spec=ProductIndexReader)
    index_reader.read.return_value = INDEX
    fee_gap_sheet = Mock(spec=FeeGapSheet)
    usecase = UpdateActualGrossProfitUseCase(
        sales_sheet=sheet,
        sales_repository=sales_repo,
        orders_repository=orders_repo,
        finances_repository=finances_repo,
        index_reader=index_reader,
        fee_gap_sheet=fee_gap_sheet,
    )
    return usecase, sheet, fee_gap_sheet, sales_repo, orders_repo, finances_repo


class TestUpdateActualGrossProfit:
    def test_writes_the_blended_profit_for_the_order_date(self) -> None:
        usecase, sheet, _, _, _, _ = _build()

        usecase.execute()

        cells_by_date = sheet.write_actual_gross_profit.call_args[0][0]
        cell = cells_by_date[ORDER_DATE][0]
        assert cell.profit == 3750.0
        assert cell.estimate == 3900.0
        assert cell.fully_settled is True

    def test_writes_the_fee_gap_sheet(self) -> None:
        usecase, _, fee_gap_sheet, _, _, _ = _build()

        usecase.execute()

        gaps = fee_gap_sheet.write.call_args[0][0]
        assert gaps[0].asin == "B00EXAMPLE"
        assert gaps[0].actual_fba_fee == 252.0
        assert gaps[0].actual_referral_fee == 98.0
        assert fee_gap_sheet.write.call_args[0][1] == {"B00EXAMPLE": "ルーペ"}

    def test_raises_without_touching_the_sheet_when_no_actuals_came_back(self) -> None:
        # ロールが外れている・API障害のときに見積を壊してはいけない。0件で正常
        # 終了すると launchd の失敗通知が鳴らない
        usecase, sheet, fee_gap_sheet, _, _, _ = _build(records=[])

        with pytest.raises(EmptyFinancesResultError):
            usecase.execute()

        sheet.write_actual_gross_profit.assert_not_called()
        fee_gap_sheet.write.assert_not_called()

    def test_window_covers_30_days_and_excludes_today(self) -> None:
        usecase, _, _, sales_repo, orders_repo, _ = _build()

        usecase.execute()

        # interval は UTC の Z 形式。+09:00 形式だと orderMetrics が何も返さない
        start, end = sales_repo.get_sales_by_date.call_args[0][1:3]
        assert start.endswith("Z") and end.endswith("Z")
        start_date = _parse_utc(start).astimezone(JST).date()
        end_date = _parse_utc(end).astimezone(JST).date()
        assert end_date == datetime.now(JST).date()
        # 実測は精算単位で約7日遅れる。14日では確定する前に窓から外れる
        assert (end_date - start_date).days == 30

    def test_counts_skus_that_are_not_on_the_sheet(self) -> None:
        usecase, _, _, _, _, _ = _build(
            records=[
                FinanceRecord("503-1", "SKU-A", quantity=3, fba_fee_amount=756.0, referral_fee_amount=294.0),
                FinanceRecord("503-1", "SKU-GONE", quantity=1, fba_fee_amount=100.0),
            ]
        )

        result = usecase.execute()

        assert result.unknown_sku_count == 1

    def test_finance_window_never_asks_for_a_future_instant(self) -> None:
        # PostedBefore に未来を渡すと SP-API は 400 を返す（実際に落ちた）
        usecase, _, _, _, _, finances_repo = _build()

        usecase.execute()

        posted_before = finances_repo.get_finance_records.call_args[0][1]
        asked = datetime.strptime(posted_before, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        # SP-API は「2分前より新しい PostedBefore」を 400 で弾く
        assert asked <= datetime.now(timezone.utc) - timedelta(minutes=2)

    def test_raises_when_nothing_could_be_written_despite_having_data(self) -> None:
        from py_src.domain.value_objects.gross_profit_write_result import (
            GrossProfitRowsNotFoundError,
        )

        usecase, sheet, _, _, _, _ = _build()
        sheet.write_actual_gross_profit.return_value = ActualProfitWriteResult(cells_written=0)

        with pytest.raises(GrossProfitRowsNotFoundError):
            usecase.execute()
