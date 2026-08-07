from unittest.mock import Mock
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.sheets.sales_data_sheet import SalesDataSheet


class TestSalesDataSheet:
    def test_append_weekly_data_writes_rows_in_expected_format(self) -> None:
        worksheet = Mock()
        sheet = SalesDataSheet(worksheet=worksheet)
        asin_sales = {
            "B00ASIN001": SalesInfo(unit_count=10, total_sales_amount=30000.0, order_count=5),
            "B00ASIN002": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        ad_spend = {"B00ASIN001": 1500.5, "B00ASIN002": 0.0}

        sheet.append_weekly_data(
            start_date="2026/4/20",
            end_date="2026/4/27",
            asin_sales=asin_sales,
            ad_spend=ad_spend,
        )

        worksheet.append_rows.assert_called_once_with([
            ["2026/4/20", "2026/4/27", "B00ASIN001", 10, 30000.0, 5, 1500.5],
            ["2026/4/20", "2026/4/27", "B00ASIN002", 2, 6000.0, 1, 0.0],
        ])

    def test_append_weekly_data_uses_zero_when_ad_spend_missing(self) -> None:
        worksheet = Mock()
        sheet = SalesDataSheet(worksheet=worksheet)
        asin_sales = {
            "B00ASIN001": SalesInfo(unit_count=3, total_sales_amount=9000.0, order_count=2),
        }
        sheet.append_weekly_data(
            start_date="2026/4/20",
            end_date="2026/4/27",
            asin_sales=asin_sales,
            ad_spend={},
        )
        worksheet.append_rows.assert_called_once_with([
            ["2026/4/20", "2026/4/27", "B00ASIN001", 3, 9000.0, 2, 0.0],
        ])

    def test_append_weekly_data_no_op_for_empty_sales(self) -> None:
        worksheet = Mock()
        sheet = SalesDataSheet(worksheet=worksheet)
        sheet.append_weekly_data(
            start_date="2026/4/20",
            end_date="2026/4/27",
            asin_sales={},
            ad_spend={},
        )
        worksheet.append_rows.assert_not_called()
