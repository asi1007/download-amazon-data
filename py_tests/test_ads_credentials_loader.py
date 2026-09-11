from pathlib import Path

import pytest

from py_src.infrastructure.api.ads_credentials_loader import load_ads_credentials


@pytest.fixture(autouse=True)
def master(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "ads-master.env"
    path.write_text(
        "AMAZON_CLIENT_ID=amzn1.application-oa2-client.abc\n"
        "AMAZON_CLIENT_SECRET=secret\n"
        "AMAZON_REFRESH_TOKEN=Atzr|refresh\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ADS_CREDENTIALS_MASTER", str(path))
    return path


class TestAdsCredentialsLoader:
    def test_資格情報は共有マスターからプロファイルは環境ファイルから(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# コメント行\n"
            "AMAZON_PROFILE_ID=1234567890\n"
            "AMAZON_REGION=FE\n"
            "GOOGLE_SHEET_NAME=Amazon広告\n"
        )

        credentials = load_ads_credentials(env_file)

        assert credentials.client_id == "amzn1.application-oa2-client.abc"
        assert credentials.refresh_token == "Atzr|refresh"
        assert credentials.profile_id == "1234567890"
        assert credentials.api_base_url == "https://advertising-api-fe.amazon.com"

    def test_プロファイルIDが無ければ落ちる(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("AMAZON_REGION=FE\n")

        with pytest.raises(ValueError, match="AMAZON_PROFILE_ID"):
            load_ads_credentials(env_file)

    def test_環境ファイルが無ければ落ちる(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_ads_credentials(tmp_path / "no-such.env")

    def test_共有マスターが無ければ落ちる(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("AMAZON_PROFILE_ID=1234567890\nAMAZON_REGION=FE\n")
        monkeypatch.setenv("ADS_CREDENTIALS_MASTER", str(tmp_path / "ない.env"))

        with pytest.raises(Exception, match="ない.env"):
            load_ads_credentials(env_file)
