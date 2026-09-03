from py_src.domain.value_objects.ads_credentials import AdsCredentials


class TestAdsCredentials:
    def test_api_base_url_for_far_east(self) -> None:
        credentials = AdsCredentials(
            client_id="id", client_secret="secret", refresh_token="token",
            profile_id="123", region="FE",
        )
        assert credentials.api_base_url == "https://advertising-api-fe.amazon.com"
