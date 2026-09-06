from datetime import datetime
from unittest.mock import Mock

import gspread
from gspread import Spreadsheet, Worksheet

from py_src.domain.value_objects.fee_gap import FeeGap
from py_src.infrastructure.sheets.fee_gap_sheet import FEE_GAP_SHEET_NAME, FeeGapSheet

UPDATED_AT = datetime(2026, 9, 5, 3, 0)
GAPS = [
    FeeGap(asin="B0GSLDK2DJ", quantity=114, estimated_referral_fee=37.4,
           actual_referral_fee=40.0, estimated_fba_fee=222.0, actual_fba_fee=356.4),
    FeeGap(asin="B0HD5T1XF1", quantity=8, estimated_referral_fee=139.0,
           actual_referral_fee=40.0, estimated_fba_fee=318.0, actual_fba_fee=251.8),
]
NAMES = {"B0GSLDK2DJ": "ルーペ", "B0HD5T1XF1": "ボール"}


def _spreadsheet(existing: bool = True) -> tuple[Mock, Mock]:
    worksheet = Mock(spec=Worksheet)
    spreadsheet = Mock(spec=Spreadsheet)
    if existing:
        spreadsheet.worksheet.return_value = worksheet
    else:
        spreadsheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound()
        spreadsheet.add_worksheet.return_value = worksheet
    return spreadsheet, worksheet


class TestFeeGapSheet:
    def test_writes_a_row_per_asin_with_a_clickable_link(self) -> None:
        spreadsheet, worksheet = _spreadsheet()

        written = FeeGapSheet(spreadsheet).write(GAPS, NAMES, UPDATED_AT)

        assert written == 2
        values = worksheet.update.call_args[0][0]
        assert values[0] == [
            "ASIN", "商品名", "個数",
            "見積 販売手数料/個", "実測 販売手数料/個", "販売手数料 差",
            "見積 FBA/個", "実測 FBA/個", "FBA 差",
            "合計 差/個", "更新",
        ]
        assert values[1][0] == (
            '=HYPERLINK("https://www.amazon.co.jp/dp/B0GSLDK2DJ","B0GSLDK2DJ")'
        )
        # 販売手数料（価格連動）と FBA手数料（価格非連動）を分けて出す
        assert values[1][1:] == [
            "ルーペ", 114, 37.4, 40.0, 2.6, 222.0, 356.4, 134.4, 137.0, "2026-09-05 03:00"
        ]

    def test_creates_the_worksheet_when_it_does_not_exist(self) -> None:
        spreadsheet, _ = _spreadsheet(existing=False)

        FeeGapSheet(spreadsheet).write(GAPS, NAMES, UPDATED_AT)

        spreadsheet.add_worksheet.assert_called_once()
        assert spreadsheet.add_worksheet.call_args.kwargs["title"] == FEE_GAP_SHEET_NAME

    def test_clears_before_writing_so_removed_asins_do_not_linger(self) -> None:
        spreadsheet, worksheet = _spreadsheet()

        FeeGapSheet(spreadsheet).write(GAPS, NAMES, UPDATED_AT)

        worksheet.clear.assert_called_once()

    def test_formulas_are_written_as_formulas(self) -> None:
        spreadsheet, worksheet = _spreadsheet()

        FeeGapSheet(spreadsheet).write(GAPS, NAMES, UPDATED_AT)

        assert worksheet.update.call_args.kwargs["value_input_option"] == "USER_ENTERED"

    def test_empty_gap_list_still_clears_and_writes_the_header(self) -> None:
        spreadsheet, worksheet = _spreadsheet()

        written = FeeGapSheet(spreadsheet).write([], {}, UPDATED_AT)

        assert written == 0
        assert len(worksheet.update.call_args[0][0]) == 1
