from unittest.mock import Mock
from py_src.infrastructure.sheets.amazon_ad_sheet import AmazonAdSheet


class TestAmazonAdSheet:
    def test_get_ad_spend_by_period_start_filters_by_start_date(self) -> None:
        worksheet = Mock()
        worksheet.get_all_values.return_value = [
            ["取得日時", "対象期間（開始）", "対象期間（終了）", "ASIN", "広告費"],
            ["2026-04-20 12:00", "2026-04-19", "2026-04-19", "B00ASIN001", "1000.5"],
            ["2026-04-20 12:00", "2026-04-19", "2026-04-19", "B00ASIN002", "500"],
            ["2026-04-21 12:00", "2026-04-20", "2026-04-20", "B00ASIN001", "999"],
        ]
        sheet = AmazonAdSheet(worksheet=worksheet)
        result = sheet.get_ad_spend_by_period_start("2026-04-19")
        assert result == {"B00ASIN001": 1000.5, "B00ASIN002": 500.0}

    def test_get_ad_spend_by_period_start_empty_when_no_match(self) -> None:
        worksheet = Mock()
        worksheet.get_all_values.return_value = [
            ["取得日時", "対象期間（開始）", "対象期間（終了）", "ASIN", "広告費"],
            ["2026-04-20 12:00", "2026-04-19", "2026-04-19", "B00ASIN001", "1000"],
        ]
        sheet = AmazonAdSheet(worksheet=worksheet)
        result = sheet.get_ad_spend_by_period_start("2026-05-01")
        assert result == {}

    def test_get_ad_spend_by_period_start_returns_empty_for_only_header(self) -> None:
        worksheet = Mock()
        worksheet.get_all_values.return_value = [
            ["取得日時", "対象期間（開始）", "対象期間（終了）", "ASIN", "広告費"],
        ]
        sheet = AmazonAdSheet(worksheet=worksheet)
        result = sheet.get_ad_spend_by_period_start("2026-04-19")
        assert result == {}

    def test_duplicate_asin_uses_last_value(self) -> None:
        worksheet = Mock()
        worksheet.get_all_values.return_value = [
            ["取得日時", "対象期間（開始）", "対象期間（終了）", "ASIN", "広告費"],
            ["2026-04-20 12:00", "2026-04-19", "2026-04-19", "B00ASIN001", "1000"],
            ["2026-04-21 12:00", "2026-04-19", "2026-04-19", "B00ASIN001", "2000"],
        ]
        sheet = AmazonAdSheet(worksheet=worksheet)
        result = sheet.get_ad_spend_by_period_start("2026-04-19")
        assert result == {"B00ASIN001": 2000.0}
