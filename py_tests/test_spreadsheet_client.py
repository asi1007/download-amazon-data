from unittest.mock import Mock, patch

from py_src.infrastructure.sheets.spreadsheet_client import (
    open_spreadsheet,
    GOOGLE_SHEETS_TIMEOUT_SECONDS,
)


class TestOpenSpreadsheet:
    @patch("py_src.infrastructure.sheets.spreadsheet_client.ServiceAccountCredentials")
    @patch("py_src.infrastructure.sheets.spreadsheet_client.gspread")
    def test_sets_timeout_on_the_client(
        self, mock_gspread: Mock, mock_creds_cls: Mock
    ) -> None:
        mock_client = Mock()
        mock_gspread.authorize.return_value = mock_client
        mock_spreadsheet = Mock()
        mock_client.open_by_key.return_value = mock_spreadsheet

        result = open_spreadsheet("creds.json", "sheet123")

        mock_client.set_timeout.assert_called_once_with(GOOGLE_SHEETS_TIMEOUT_SECONDS)
        mock_client.open_by_key.assert_called_once_with("sheet123")
        assert result is mock_spreadsheet

    @patch("py_src.infrastructure.sheets.spreadsheet_client.ServiceAccountCredentials")
    @patch("py_src.infrastructure.sheets.spreadsheet_client.gspread")
    def test_timeout_is_set_before_the_hangable_open_by_key_call(
        self, mock_gspread: Mock, mock_creds_cls: Mock
    ) -> None:
        mock_client = Mock()
        call_order: list[str] = []
        mock_client.set_timeout.side_effect = lambda *_args: call_order.append("set_timeout")
        mock_client.open_by_key.side_effect = lambda *_args: call_order.append("open_by_key")
        mock_gspread.authorize.return_value = mock_client

        open_spreadsheet("creds.json", "sheet123")

        assert call_order == ["set_timeout", "open_by_key"]
