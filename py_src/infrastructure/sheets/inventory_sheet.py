from __future__ import annotations
from datetime import datetime, timezone, timedelta
from gspread import Worksheet
from py_src.domain.value_objects.inventory_summary import InventorySummary

JST = timezone(timedelta(hours=9))

HEADERS = [
    "ASIN",
    "SKU",
    "販売価格",
    "販売可能\n(fulfillableQuantity)",
    "納品準備中\n(inboundWorkingQuantity)",
    "納品中\n(inboundShippedQuantity)",
    "受領中\n(inboundReceivingQuantity)",
    "予約済合計\n(totalReservedQuantity)",
    "注文確保\n(pendingCustomerOrderQuantity)",
    "転送中\n(pendingTransshipmentQuantity)",
    "処理中\n(fcProcessingQuantity)",
    "最終更新日時",
]
COLUMN_COUNT = len(HEADERS)


class InventorySheet:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    def write_inventory_data(self, summaries: list[InventorySummary]) -> None:
        timestamp = datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S")
        rows = [s.to_row(timestamp) for s in summaries]

        self._worksheet.update("A1", [HEADERS])
        self._clear_existing_rows()
        if rows:
            end_col_letter = chr(ord("A") + COLUMN_COUNT - 1)
            self._worksheet.update(f"A2:{end_col_letter}{len(rows) + 1}", rows)

    def _clear_existing_rows(self) -> None:
        last_row = self._worksheet.row_count
        if last_row < 2:
            return
        end_col_letter = chr(ord("A") + COLUMN_COUNT - 1)
        self._worksheet.batch_clear([f"A2:{end_col_letter}{last_row}"])
