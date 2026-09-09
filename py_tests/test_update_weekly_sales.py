from datetime import date, datetime, timezone, timedelta
from unittest.mock import Mock
from py_src.usecases.update_weekly_sales import UpdateWeeklySalesUseCase
from sales_data.domain.value_objects.sales_info import SalesInfo

JST = timezone(timedelta(hours=9))


class TestUpdateWeeklySalesUseCase:
    def test_execute_writes_weekly_sales_with_ad_spend(self) -> None:
        mock_sales_sheet = Mock()
        mock_sales_sheet.get_asin_list.return_value = ["B00ASIN001", "B00ASIN002"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_weekly_sales.return_value = {
            "B00ASIN001": SalesInfo(unit_count=10, total_sales_amount=30000.0, order_count=5),
            "B00ASIN002": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        mock_ad_sheet = Mock()
        mock_ad_sheet.get_ad_spend_by_period_start.return_value = {"B00ASIN001": 1500.0}
        mock_data_sheet = Mock()

        today = date(2026, 4, 29)
        usecase = UpdateWeeklySalesUseCase(
            sales_sheet=mock_sales_sheet,
            sales_repository=mock_sales_repo,
            ad_sheet=mock_ad_sheet,
            sales_data_sheet=mock_data_sheet,
            today=today,
        )
        usecase.execute()

        mock_sales_repo.get_weekly_sales.assert_called_once()
        mock_ad_sheet.get_ad_spend_by_period_start.assert_called_once_with("2026-04-20")
        mock_data_sheet.append_weekly_data.assert_called_once_with(
            start_date="2026/4/20",
            end_date="2026/4/27",
            asin_sales=mock_sales_repo.get_weekly_sales.return_value,
            ad_spend={"B00ASIN001": 1500.0},
        )

    def test_weekly_range_is_previous_monday_week(self) -> None:
        mock_sales_sheet = Mock()
        mock_sales_sheet.get_asin_list.return_value = ["B00ASIN001"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_weekly_sales.return_value = {}
        mock_ad_sheet = Mock()
        mock_ad_sheet.get_ad_spend_by_period_start.return_value = {}
        mock_data_sheet = Mock()

        today = date(2026, 4, 29)
        usecase = UpdateWeeklySalesUseCase(
            sales_sheet=mock_sales_sheet,
            sales_repository=mock_sales_repo,
            ad_sheet=mock_ad_sheet,
            sales_data_sheet=mock_data_sheet,
            today=today,
        )
        usecase.execute()

        args = mock_sales_repo.get_weekly_sales.call_args
        start_iso = args.kwargs["start_date"]
        end_iso = args.kwargs["end_date"]
        start = datetime.strptime(start_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        end = datetime.strptime(end_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        start_jst = start.astimezone(JST)
        end_jst = end.astimezone(JST)
        assert start_jst.date() == date(2026, 4, 20)
        assert end_jst.date() == date(2026, 4, 27)

    def test_weekly_range_when_today_is_monday(self) -> None:
        mock_sales_sheet = Mock()
        mock_sales_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock()
        mock_sales_repo.get_weekly_sales.return_value = {}
        mock_ad_sheet = Mock()
        mock_ad_sheet.get_ad_spend_by_period_start.return_value = {}
        mock_data_sheet = Mock()

        today = date(2026, 4, 27)
        usecase = UpdateWeeklySalesUseCase(
            sales_sheet=mock_sales_sheet,
            sales_repository=mock_sales_repo,
            ad_sheet=mock_ad_sheet,
            sales_data_sheet=mock_data_sheet,
            today=today,
        )
        usecase.execute()

        mock_ad_sheet.get_ad_spend_by_period_start.assert_called_once_with("2026-04-20")

    def test_weekly_range_when_today_is_sunday(self) -> None:
        mock_sales_sheet = Mock()
        mock_sales_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock()
        mock_sales_repo.get_weekly_sales.return_value = {}
        mock_ad_sheet = Mock()
        mock_ad_sheet.get_ad_spend_by_period_start.return_value = {}
        mock_data_sheet = Mock()

        today = date(2026, 4, 26)
        usecase = UpdateWeeklySalesUseCase(
            sales_sheet=mock_sales_sheet,
            sales_repository=mock_sales_repo,
            ad_sheet=mock_ad_sheet,
            sales_data_sheet=mock_data_sheet,
            today=today,
        )
        usecase.execute()

        mock_ad_sheet.get_ad_spend_by_period_start.assert_called_once_with("2026-04-13")
