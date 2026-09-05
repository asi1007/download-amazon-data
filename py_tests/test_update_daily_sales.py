from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from py_src.usecases.update_daily_sales import UpdateDailySalesUseCase
from py_src.domain.repositories.price_repository import PriceRepository
from py_src.domain.repositories.sales_repository import SalesRepository
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.unit_costs import UnitCosts
from py_src.infrastructure.sheets.sales_sheet import SalesSheet
from py_src.infrastructure.sheets.unit_cost_reader import UnitCostReader

JST = timezone(timedelta(hours=9))


def _no_cost_reader() -> Mock:
    cost_reader = Mock(spec=UnitCostReader)
    cost_reader.read.return_value = {}
    return cost_reader


class TestUpdateDailySalesUseCase:
    def test_execute_writes_sales_and_prices(self) -> None:
        mock_sheet = Mock(spec=SalesSheet)
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE", "B00EXAMPLF"]
        mock_sales_repo = Mock(spec=SalesRepository)
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
            "B00EXAMPLF": SalesInfo(unit_count=1, total_sales_amount=3000.0, order_count=1),
        }
        mock_price_repo = Mock(spec=PriceRepository)
        mock_price_repo.get_competitive_prices.return_value = {"B00EXAMPLE": 3200.0, "B00EXAMPLF": 1600.0}

        usecase = UpdateDailySalesUseCase(
            sales_sheet=mock_sheet,
            sales_repository=mock_sales_repo,
            price_repository=mock_price_repo,
            cost_reader=_no_cost_reader(),
        )
        usecase.execute()

        mock_sheet.get_asin_list.assert_called_once()
        mock_sales_repo.get_daily_sales.assert_called_once()
        mock_sheet.write_sales_nums.assert_called_once()
        mock_price_repo.get_competitive_prices.assert_called_once_with(["B00EXAMPLE", "B00EXAMPLF"])
        mock_sheet.write_prices.assert_called_once()

    def test_yesterday_date_range_is_valid(self) -> None:
        mock_sheet = Mock(spec=SalesSheet)
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock(spec=SalesRepository)
        mock_sales_repo.get_daily_sales.return_value = {}
        mock_price_repo = Mock(spec=PriceRepository)
        mock_price_repo.get_competitive_prices.return_value = {}

        usecase = UpdateDailySalesUseCase(
            sales_sheet=mock_sheet,
            sales_repository=mock_sales_repo,
            price_repository=mock_price_repo,
            cost_reader=_no_cost_reader(),
        )
        usecase.execute()

        args = mock_sales_repo.get_daily_sales.call_args
        start_date = args[1].get("start_date", args[0][1] if len(args[0]) > 1 else None)
        end_date = args[1].get("end_date", args[0][2] if len(args[0]) > 2 else None)
        assert start_date.endswith("Z")
        assert end_date.endswith("Z")
        assert start_date < end_date

    def test_empty_asin_list(self) -> None:
        mock_sheet = Mock(spec=SalesSheet)
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock(spec=SalesRepository)
        mock_sales_repo.get_daily_sales.return_value = {}
        mock_price_repo = Mock(spec=PriceRepository)
        mock_price_repo.get_competitive_prices.return_value = {}

        usecase = UpdateDailySalesUseCase(
            sales_sheet=mock_sheet,
            sales_repository=mock_sales_repo,
            price_repository=mock_price_repo,
            cost_reader=_no_cost_reader(),
        )
        usecase.execute()

        expected_yesterday = (datetime.now(JST) - timedelta(days=1)).date()
        mock_sheet.write_sales_nums.assert_called_once_with({}, target_date=expected_yesterday)
        mock_price_repo.get_competitive_prices.assert_called_once_with([])

    def test_writes_estimated_gross_profit_after_units(self) -> None:
        sales_sheet = Mock(spec=SalesSheet)
        sales_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        cost_reader = Mock(spec=UnitCostReader)
        cost_reader.read.return_value = {
            "B00EXAMPLE": UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)
        }
        sales_repository = Mock(spec=SalesRepository)
        sales_repository.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=3, total_sales_amount=3000.0)
        }
        price_repository = Mock(spec=PriceRepository)
        price_repository.get_competitive_prices.return_value = {}
        usecase = UpdateDailySalesUseCase(
            sales_sheet=sales_sheet,
            sales_repository=sales_repository,
            price_repository=price_repository,
            cost_reader=cost_reader,
        )

        usecase.execute()

        written = sales_sheet.write_gross_profit.call_args[0][0]
        assert written == {"B00EXAMPLE": 1200.0}

    def test_asin_with_missing_costs_is_absent_from_the_write(self) -> None:
        sales_sheet = Mock(spec=SalesSheet)
        sales_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        cost_reader = Mock(spec=UnitCostReader)
        cost_reader.read.return_value = {"B00EXAMPLE": UnitCosts(None, 300.0, 200.0)}
        sales_repository = Mock(spec=SalesRepository)
        sales_repository.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=3, total_sales_amount=3000.0)
        }
        price_repository = Mock(spec=PriceRepository)
        price_repository.get_competitive_prices.return_value = {}
        usecase = UpdateDailySalesUseCase(
            sales_sheet=sales_sheet,
            sales_repository=sales_repository,
            price_repository=price_repository,
            cost_reader=cost_reader,
        )

        usecase.execute()

        assert sales_sheet.write_gross_profit.call_args[0][0] == {}

    def test_units_are_written_before_profit(self) -> None:
        # 粗利益は売上個数と同じ列に書くので、列を解決する write_sales_nums が先
        sales_sheet = Mock(spec=SalesSheet)
        sales_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        cost_reader = Mock(spec=UnitCostReader)
        cost_reader.read.return_value = {
            "B00EXAMPLE": UnitCosts(selling_fee=1.0, fba_fee=1.0, cost=1.0)
        }
        sales_repository = Mock(spec=SalesRepository)
        sales_repository.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=1, total_sales_amount=10.0)
        }
        price_repository = Mock(spec=PriceRepository)
        price_repository.get_competitive_prices.return_value = {}
        calls: list[str] = []
        sales_sheet.write_sales_nums.side_effect = lambda *a, **k: calls.append("units")
        sales_sheet.write_prices.side_effect = lambda *a, **k: calls.append("prices")
        sales_sheet.write_gross_profit.side_effect = lambda *a, **k: calls.append("profit")
        usecase = UpdateDailySalesUseCase(
            sales_sheet=sales_sheet,
            sales_repository=sales_repository,
            price_repository=price_repository,
            cost_reader=cost_reader,
        )

        usecase.execute()

        # 粗利益は価格のあとに書く。原価列の読み取りが落ちても価格列を巻き添えにしない
        assert calls == ["units", "prices", "profit"]
