import pytest
from unittest.mock import Mock, patch
from gspread.exceptions import APIError
import main


def _api_error(code: int, message: str) -> APIError:
    response = Mock()
    response.json.return_value = {
        "error": {"code": code, "message": message, "status": "UNAVAILABLE"}
    }
    return APIError(response)


@patch("py_src.infrastructure.sheets.retry.time.sleep")
@patch("py_src.infrastructure.sheets.spreadsheet_client.ServiceAccountCredentials")
@patch("py_src.infrastructure.sheets.spreadsheet_client.gspread")
class TestOpenSpreadsheetSurvivesTransientOutage:
    def test_retries_when_sheets_api_is_unavailable(
        self, mock_gspread: Mock, mock_credentials: Mock, mock_sleep: Mock
    ) -> None:
        spreadsheet = Mock()
        client = Mock()
        client.open_by_key.side_effect = [
            _api_error(503, "The service is currently unavailable."),
            spreadsheet,
        ]
        mock_gspread.authorize.return_value = client

        assert main._open_spreadsheet() is spreadsheet
        assert client.open_by_key.call_count == 2

    def test_does_not_retry_when_access_is_denied(
        self, mock_gspread: Mock, mock_credentials: Mock, mock_sleep: Mock
    ) -> None:
        client = Mock()
        client.open_by_key.side_effect = _api_error(403, "The caller does not have permission")
        mock_gspread.authorize.return_value = client

        with pytest.raises(APIError):
            main._open_spreadsheet()
        assert client.open_by_key.call_count == 1
