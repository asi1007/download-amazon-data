from pathlib import Path
import pytest
from py_src.domain.value_objects.ads_credentials import AdsCredentials


class TestAdsCredentials:
    def test_api_base_url_for_far_east(self) -> None:
        credentials = AdsCredentials(
            client_id="id", client_secret="secret", refresh_token="token",
            profile_id="123", region="FE",
        )
        assert credentials.api_base_url == "https://advertising-api-fe.amazon.com"

    def test_from_env_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# コメント行\n"
            "AMAZON_CLIENT_ID=amzn1.application-oa2-client.abc\n"
            "AMAZON_CLIENT_SECRET=secret\n"
            "AMAZON_REFRESH_TOKEN=Atzr|refresh\n"
            "AMAZON_PROFILE_ID=1234567890\n"
            "AMAZON_REGION=FE\n"
            "GOOGLE_SHEET_NAME=Amazon広告\n"
        )
        credentials = AdsCredentials.from_env_file(env_file)

        assert credentials.client_id == "amzn1.application-oa2-client.abc"
        assert credentials.refresh_token == "Atzr|refresh"
        assert credentials.profile_id == "1234567890"
        assert credentials.api_base_url == "https://advertising-api-fe.amazon.com"

    def test_from_env_file_missing_key_raises(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("AMAZON_CLIENT_ID=abc\n")

        with pytest.raises(ValueError, match="AMAZON_CLIENT_SECRET"):
            AdsCredentials.from_env_file(env_file)

    def test_from_env_file_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            AdsCredentials.from_env_file(tmp_path / "no-such.env")
