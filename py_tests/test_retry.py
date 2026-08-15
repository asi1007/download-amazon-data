import pytest
import requests
from unittest.mock import Mock, patch
from gspread.exceptions import APIError
from py_src.infrastructure.sheets.retry import retry_on_transient_error


def _api_error(code: int, message: str) -> APIError:
    response = Mock()
    response.json.return_value = {
        "error": {"code": code, "message": message, "status": "UNAVAILABLE"}
    }
    return APIError(response)


def _failing_times(failures: list[Exception]) -> tuple[callable, list[int]]:
    attempts: list[int] = []

    @retry_on_transient_error
    def operation() -> str:
        attempts.append(len(attempts) + 1)
        if len(attempts) <= len(failures):
            raise failures[len(attempts) - 1]
        return "ok"

    return operation, attempts


@patch("py_src.infrastructure.sheets.retry.time.sleep")
class TestRetriesOnTransientSheetsApiError:
    def test_retries_when_sheets_api_is_unavailable(self, mock_sleep: Mock) -> None:
        unavailable = _api_error(503, "The service is currently unavailable.")
        operation, attempts = _failing_times([unavailable, unavailable])

        assert operation() == "ok"
        assert len(attempts) == 3

    def test_retries_when_rate_limited(self, mock_sleep: Mock) -> None:
        rate_limited = _api_error(429, "Quota exceeded")
        operation, attempts = _failing_times([rate_limited])

        assert operation() == "ok"
        assert len(attempts) == 2

    def test_reraises_transient_error_after_exhausting_attempts(self, mock_sleep: Mock) -> None:
        unavailable = _api_error(503, "The service is currently unavailable.")
        operation, attempts = _failing_times([unavailable] * 5)

        with pytest.raises(APIError):
            operation()
        assert len(attempts) == 3


@patch("py_src.infrastructure.sheets.retry.time.sleep")
class TestDoesNotRetryOnPermanentError:
    def test_permission_denied_is_raised_immediately(self, mock_sleep: Mock) -> None:
        forbidden = _api_error(403, "The caller does not have permission")
        operation, attempts = _failing_times([forbidden])

        with pytest.raises(APIError):
            operation()
        assert len(attempts) == 1
        mock_sleep.assert_not_called()

    def test_not_found_is_raised_immediately(self, mock_sleep: Mock) -> None:
        not_found = _api_error(404, "Requested entity was not found")
        operation, attempts = _failing_times([not_found])

        with pytest.raises(APIError):
            operation()
        assert len(attempts) == 1


@patch("py_src.infrastructure.sheets.retry.time.sleep")
class TestBacksOffBetweenAttempts:
    def test_waits_longer_after_each_failed_attempt(self, mock_sleep: Mock) -> None:
        reset = requests.exceptions.ConnectionError("Connection reset by peer")
        operation, _ = _failing_times([reset, reset])

        operation()

        waited = [call.args[0] for call in mock_sleep.call_args_list]
        assert waited == sorted(waited)
        assert waited[0] < waited[1]
