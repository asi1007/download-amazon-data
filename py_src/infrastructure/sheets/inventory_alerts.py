from __future__ import annotations
from dataclasses import dataclass

from gspread import Worksheet

from py_src.infrastructure.sheets.label_rows import HEADER_ROW, find_column
from py_src.infrastructure.sheets.retry import retry_on_transient_error

WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
# 在庫切れが近いほど手を打つ余地が無い。FBA在庫日数だけ一段強くする
CRITICAL_FORMAT = {
    "backgroundColor": {"red": 0.78, "green": 0.16, "blue": 0.13},
    "textFormat": {"foregroundColor": WHITE, "bold": True},
}
WARNING_FORMAT = {"backgroundColor": {"red": 0.98, "green": 0.85, "blue": 0.83}}


@dataclass(frozen=True)
class InventoryAlert:
    header: str
    threshold: int
    cell_format: dict


ALERTS: tuple[InventoryAlert, ...] = (
    InventoryAlert("FBA在庫日数", 14, CRITICAL_FORMAT),
    InventoryAlert("在庫日数", 72, WARNING_FORMAT),
    InventoryAlert("目標売上在庫日数", 72, WARNING_FORMAT),
)
# 強調しないセルは白に戻す。条件付き書式を消したときに下地のピンクが露出した
NORMALIZED_HEADERS: tuple[str, ...] = (
    "FBA在庫日数",
    "昨日売上2週分",
    "3日間平均2周分",
    "週平均2周分",
    "在庫日数",
    "目標売上在庫日数",
)


def build_alert_rule(sheet_id: int, column: int, last_row: int, alert: InventoryAlert) -> dict:
    return {
        "ranges": [{
            "sheetId": sheet_id,
            "startRowIndex": HEADER_ROW,
            "endRowIndex": last_row,
            "startColumnIndex": column - 1,
            "endColumnIndex": column,
        }],
        "booleanRule": {
            "condition": {
                "type": "NUMBER_LESS_THAN_EQ",
                "values": [{"userEnteredValue": str(alert.threshold)}],
            },
            "format": alert.cell_format,
        },
    }


class InventoryAlerts:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    @retry_on_transient_error
    def apply(self) -> int:
        headers = self._worksheet.row_values(HEADER_ROW)
        sheet_id = self._worksheet.id
        last_row = self._worksheet.row_count
        columns = {alert.header: find_column(headers, alert.header) for alert in ALERTS}

        requests = self._delete_own_rules(sheet_id, set(columns.values()))
        requests += [
            {"addConditionalFormatRule": {"rule": build_alert_rule(
                sheet_id, columns[alert.header], last_row, alert), "index": 0}}
            for alert in ALERTS
        ]
        requests += [
            self._normalize_request(sheet_id, find_column(headers, header), last_row)
            for header in NORMALIZED_HEADERS
        ]
        self._worksheet.spreadsheet.batch_update({"requests": requests})
        return len(ALERTS)

    @staticmethod
    def _normalize_request(sheet_id: int, column: int, last_row: int) -> dict:
        return {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": HEADER_ROW,
                    "endRowIndex": last_row,
                    "startColumnIndex": column - 1,
                    "endColumnIndex": column,
                },
                "cell": {"userEnteredFormat": {"backgroundColor": WHITE}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        }

    def _delete_own_rules(self, sheet_id: int, columns: set[int]) -> list[dict]:
        # 自分が入れた規則だけを消す。全件削除するとシートに元からある書式まで
        # 巻き込む（実際にやってしまった）。index を消すと後ろが繰り上がるので降順
        metadata = self._worksheet.spreadsheet.fetch_sheet_metadata(
            {"fields": "sheets(properties(sheetId),conditionalFormats(ranges,booleanRule))"}
        )
        for sheet in metadata.get("sheets", []):
            if sheet.get("properties", {}).get("sheetId") != sheet_id:
                continue
            own = [
                index
                for index, rule in enumerate(sheet.get("conditionalFormats", []))
                if _is_own_alert(rule, columns)
            ]
            return [
                {"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": index}}
                for index in sorted(own, reverse=True)
            ]
        return []


def _is_own_alert(rule: dict, columns: set[int]) -> bool:
    condition = rule.get("booleanRule", {}).get("condition", {})
    if condition.get("type") != "NUMBER_LESS_THAN_EQ":
        return False
    ranges = rule.get("ranges", [])
    return bool(ranges) and all(
        r.get("startColumnIndex", -1) + 1 in columns
        and r.get("endColumnIndex") == r.get("startColumnIndex", 0) + 1
        for r in ranges
    )
