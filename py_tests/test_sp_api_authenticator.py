import pytest
import requests
from unittest.mock import Mock, patch
from py_src.infrastructure.api.sp_api_authenticator import (
    SpApiAuthenticator,
    LWA_AUTH_TIMEOUT_SECONDS,
    SP_API_REQUEST_TIMEOUT_SECONDS,
)


def _make_response(json_data: dict, status_code: int = 200) -> Mock:
    resp = Mock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = Mock()
    return resp


class TestSpApiAuthenticator:
    def test_authenticate(self) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "test_token"})
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()
        assert auth.headers()["x-amz-access-token"] == "test_token"

    def test_headers_format(self) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "abc"})
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()
        h = auth.headers()
        assert h["Accept"] == "application/json"
        assert h["Content-Type"] == "application/json"

    @patch("py_src.infrastructure.api.sp_api_authenticator.time.sleep")
    def test_request_success(self, mock_sleep: Mock) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "token"})
        session.request.return_value = _make_response({"data": "ok"})
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()
        resp = auth.request("GET", "https://example.com/api")
        assert resp.json() == {"data": "ok"}

    @patch("py_src.infrastructure.api.sp_api_authenticator.time.sleep")
    def test_request_retries_on_429(self, mock_sleep: Mock) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "token"})
        rate_limited = _make_response({}, status_code=429)
        success = _make_response({"data": "ok"})
        session.request.side_effect = [rate_limited, success]
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()
        resp = auth.request("GET", "https://example.com/api")
        assert resp.json() == {"data": "ok"}

    @patch("py_src.infrastructure.api.sp_api_authenticator.time.sleep")
    def test_request_reauthenticates_on_403(self, mock_sleep: Mock) -> None:
        session = Mock()
        auth_resp1 = _make_response({"access_token": "token1"})
        auth_resp2 = _make_response({"access_token": "token2"})
        session.post.side_effect = [auth_resp1, auth_resp2]
        forbidden = _make_response({}, status_code=403)
        success = _make_response({"data": "ok"})
        session.request.side_effect = [forbidden, success]
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()
        resp = auth.request("GET", "https://example.com/api")
        assert resp.json() == {"data": "ok"}
        assert session.post.call_count == 2

    @patch("py_src.infrastructure.api.sp_api_authenticator.time.sleep")
    def test_persistent_403_gives_up_instead_of_looping_forever(
        self, mock_sleep: Mock
    ) -> None:
        # Finances のロールが付いていない・refresh_token が失効している等で 403 が
        # 続く場合、回数制限が無いと SP-API を叩き続けるタイトループになる
        # （19時間ハングと同じ、誰にも通知されない無音の暴走）
        session = Mock()
        session.post.return_value = _make_response({"access_token": "token"})
        forbidden = _make_response({}, status_code=403)
        forbidden.raise_for_status.side_effect = requests.exceptions.HTTPError("403")
        session.request.return_value = forbidden
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()

        with pytest.raises(requests.exceptions.HTTPError):
            auth.request("GET", "https://example.com/api", max_retries=5)

        assert session.request.call_count == 5

    @patch("py_src.infrastructure.api.sp_api_authenticator.time.sleep")
    def test_request_retries_on_connection_error(self, mock_sleep: Mock) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "token"})
        success = _make_response({"data": "ok"})
        session.request.side_effect = [
            requests.exceptions.ConnectionError("Connection reset by peer"),
            success,
        ]
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()
        resp = auth.request("GET", "https://example.com/api")
        assert resp.json() == {"data": "ok"}

    @patch("py_src.infrastructure.api.sp_api_authenticator.time.sleep")
    def test_request_retries_on_timeout(self, mock_sleep: Mock) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "token"})
        success = _make_response({"data": "ok"})
        session.request.side_effect = [
            requests.exceptions.Timeout("Read timed out"),
            success,
        ]
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()
        resp = auth.request("GET", "https://example.com/api")
        assert resp.json() == {"data": "ok"}
        assert session.request.call_count == 2

    @patch("py_src.infrastructure.api.sp_api_authenticator.time.sleep")
    def test_request_raises_after_persistent_timeouts(self, mock_sleep: Mock) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "token"})
        session.request.side_effect = requests.exceptions.Timeout("Read timed out")
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()
        with pytest.raises(requests.exceptions.Timeout):
            auth.request("GET", "https://example.com/api")
        assert session.request.call_count == 5

    @patch("py_src.infrastructure.api.sp_api_authenticator.time.sleep")
    def test_request_raises_after_persistent_connection_errors(self, mock_sleep: Mock) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "token"})
        session.request.side_effect = requests.exceptions.ConnectionError("reset")
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()
        with pytest.raises(requests.exceptions.ConnectionError):
            auth.request("GET", "https://example.com/api")

    def test_authenticate_passes_timeout_to_session(self) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "test_token"})
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()
        assert session.post.call_args.kwargs["timeout"] == LWA_AUTH_TIMEOUT_SECONDS

    @patch("py_src.infrastructure.api.sp_api_authenticator.time.sleep")
    def test_request_passes_timeout_to_session(self, mock_sleep: Mock) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "token"})
        session.request.return_value = _make_response({"data": "ok"})
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()
        auth.request("GET", "https://example.com/api")
        assert session.request.call_args.kwargs["timeout"] == SP_API_REQUEST_TIMEOUT_SECONDS

    def test_authenticate_failure_raises(self) -> None:
        session = Mock()
        resp = Mock()
        resp.raise_for_status.side_effect = Exception("401 Unauthorized")
        session.post.return_value = resp
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        with pytest.raises(Exception, match="401"):
            auth.authenticate()
