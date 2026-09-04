import pytest
import requests
from unittest.mock import Mock, patch
from gspread.utils import rowcol_to_a1
from py_src.infrastructure.sheets.sales_sheet import SalesSheet, HEADER_ROW
from py_src.domain.value_objects.sales_info import SalesInfo

HEADERS = ["", "目標販売数", "", "", "自社価格"]
RUN_DATE = (2026, 8, 10)
YESTERDAY_SERIAL = 46243


def _freeze_run_date_to(mock_datetime: Mock) -> None:
    from datetime import datetime as real_datetime, timezone, timedelta

    mock_datetime.now.return_value = real_datetime(
        *RUN_DATE, 1, 0, tzinfo=timezone(timedelta(hours=9))
    )
    mock_datetime.side_effect = real_datetime


def _create_sheet(header_serials: list) -> tuple[SalesSheet, Mock]:
    # 実運用の行構成（行1〜4は予約行、ASINは行5以降）を再現する。
    sales_ws = Mock()
    sales_ws.row_values.side_effect = [HEADERS, header_serials]
    sales_ws.col_values.return_value = ["header", "", "合計", "header4", "B00EXAMPLE"]
    sheet = SalesSheet(sales_worksheet=sales_ws)
    sheet.get_asin_list()
    return sheet, sales_ws


@patch("py_src.infrastructure.sheets.sales_sheet.datetime")
class TestColumnIsResolvedIdempotently:
    def _freeze_yesterday(self, mock_datetime: Mock) -> None:
        _freeze_run_date_to(mock_datetime)

    def test_inserts_column_labeled_with_the_target_date(self, mock_datetime: Mock) -> None:
        self._freeze_yesterday(mock_datetime)
        sheet, sales_ws = _create_sheet(["", "目標販売数", 46242, 46241])

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=2)})

        sales_ws.insert_cols.assert_called_once_with(
            [[YESTERDAY_SERIAL, "", "", YESTERDAY_SERIAL]], 3
        )

    def test_reuses_existing_column_for_the_target_date(self, mock_datetime: Mock) -> None:
        self._freeze_yesterday(mock_datetime)
        sheet, sales_ws = _create_sheet(["", "目標販売数", YESTERDAY_SERIAL, 46242])

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=2)})

        sales_ws.insert_cols.assert_not_called()
        requests_sent = sales_ws.batch_update.call_args_list[0][0][0]
        written_ranges = {r["range"] for r in requests_sent}
        assert rowcol_to_a1(HEADER_ROW, 3) in written_ranges

    def test_reuses_column_found_further_right(self, mock_datetime: Mock) -> None:
        self._freeze_yesterday(mock_datetime)
        sheet, sales_ws = _create_sheet(["", "目標販売数", 46250, YESTERDAY_SERIAL, 46242])

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=2)})

        sales_ws.insert_cols.assert_not_called()
        requests_sent = sales_ws.batch_update.call_args_list[0][0][0]
        written_ranges = {r["range"] for r in requests_sent}
        assert rowcol_to_a1(HEADER_ROW, 4) in written_ranges


@patch("py_src.infrastructure.sheets.retry.time.sleep")
@patch("py_src.infrastructure.sheets.sales_sheet.datetime")
class TestWriteRetriesOnConnectionError:
    def _freeze_yesterday(self, mock_datetime: Mock) -> None:
        _freeze_run_date_to(mock_datetime)

    def test_retries_until_write_succeeds(self, mock_datetime: Mock, mock_sleep: Mock) -> None:
        self._freeze_yesterday(mock_datetime)
        sales_ws = Mock()
        sales_ws.row_values.side_effect = [
            HEADERS, ["", "目標販売数", 46242], ["", "目標販売数", 46242],
        ]
        sales_ws.col_values.return_value = ["header", "", "合計", "header4", "B00EXAMPLE"]
        sales_ws.insert_cols.side_effect = [
            requests.exceptions.ConnectionError("Connection reset by peer"), None,
        ]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=2)})

        sales_ws.batch_update.assert_called_once()

    def test_does_not_insert_twice_when_write_fails_after_insert(
        self, mock_datetime: Mock, mock_sleep: Mock
    ) -> None:
        self._freeze_yesterday(mock_datetime)
        sales_ws = Mock()
        sales_ws.row_values.side_effect = [
            HEADERS,
            ["", "目標販売数", 46242],
            ["", "目標販売数", YESTERDAY_SERIAL, 46242],
        ]
        sales_ws.col_values.return_value = ["header", "", "合計", "header4", "B00EXAMPLE"]
        sales_ws.batch_update.side_effect = [
            requests.exceptions.ConnectionError("Connection reset by peer"), None,
        ]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=2)})

        assert sales_ws.insert_cols.call_count == 1
        assert sales_ws.batch_update.call_count == 2

    def test_reraises_after_exhausting_attempts(self, mock_datetime: Mock, mock_sleep: Mock) -> None:
        self._freeze_yesterday(mock_datetime)
        sales_ws = Mock()
        sales_ws.row_values.return_value = HEADERS
        sales_ws.col_values.return_value = ["header", "", "合計", "header4", "B00EXAMPLE"]
        sales_ws.batch_update.side_effect = requests.exceptions.ConnectionError("reset")
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        with pytest.raises(requests.exceptions.ConnectionError):
            sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=2)})

    def test_write_prices_also_retries(self, mock_datetime: Mock, mock_sleep: Mock) -> None:
        self._freeze_yesterday(mock_datetime)
        sales_ws = Mock()
        sales_ws.row_values.return_value = HEADERS
        sales_ws.col_values.return_value = ["header", "", "合計", "header4", "B00EXAMPLE"]
        sales_ws.get_notes.return_value = [["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=1)})

        calls_before_write_prices = sales_ws.batch_update.call_count
        sales_ws.batch_update.side_effect = [
            requests.exceptions.ConnectionError("reset"), None,
        ]

        sheet.write_prices({"B00EXAMPLE": 3000.0})

        assert sales_ws.batch_update.call_count - calls_before_write_prices == 2
