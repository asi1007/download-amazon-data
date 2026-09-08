from __future__ import annotations
from datetime import datetime, date, timezone, timedelta
from gspread import Worksheet
from gspread.utils import rowcol_to_a1, a1_range_to_grid_range, ValueRenderOption
from py_src.domain.value_objects.actual_profit_cell import (
    ActualProfitCell,
    ActualProfitWriteResult,
)
from py_src.domain.value_objects.gross_profit_write_result import (
    GrossProfitRowsNotFoundError,
    GrossProfitWriteResult,
)
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.sheets.label_rows import (
    ASIN_COLUMN,
    GROSS_PROFIT_ROW_LABEL,
    OPERATING_PROFIT_ROW_LABEL,
    AD_COST_ROW_LABEL,
    K_YEN_NUMBER_FORMAT,
    PRODUCT_NAME_HEADER,
    bind_label_rows,
    date_serial as label_date_serial,
    find_column as find_label_column,
    read_date_columns,
)
from py_src.infrastructure.sheets.price_change_colors import (
    PriceChangeCells,
    classify_price_changes as classify_from_notes,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error

JST = timezone(timedelta(hours=9))
HEADER_ROW = 4
TOTAL_AMOUNT_ROW = 3
# 行1〜4（日付ラベル・取得時刻・総売上）は予約行。ASINは必ず行5以降にある前提で
# `row > HEADER_ROW` によりASINループの書き込みから一括で除外する。
FETCH_TIME_ROW = 2
SHEETS_EPOCH = datetime(1899, 12, 30)
DATE_LABEL_FORMAT = {"numberFormat": {"type": "DATE", "pattern": "dd"}}
# 行2（営業利益の合計）と行3（総売上）。千円単位で表示するが単位の文字は付けない
# （数字と単位が混ざると桁が読み取りにくい）。日付ラベルより一段小さくする
SUMMARY_FONT_SIZE = 8
TOTAL_AMOUNT_FORMAT = {
    "numberFormat": {"type": "NUMBER", "pattern": "#,##0,"},
    "textFormat": {"fontSize": SUMMARY_FONT_SIZE},
}
# 値下げは赤、値上げは青。背景色ではなく文字色で塗る。売上個数セルには
# 個数の多寡を表すカラースケール（apply_gradients.py）が掛かっており、
# 条件付き書式は直接指定の背景色を上書きするため、背景に塗っても見えない
CHEAPER_FORMAT = {
    "textFormat": {"foregroundColor": {"red": 0.8, "green": 0.0, "blue": 0.0}, "bold": True}
}
PRICIER_FORMAT = {
    "textFormat": {"foregroundColor": {"red": 0.0, "green": 0.2, "blue": 0.8}, "bold": True}
}
# 価格変動の塗り分けだけを消す。フォントサイズなど他の書式は残す
PRICE_CHANGE_STYLE_FIELDS = (
    "userEnteredFormat.backgroundColor,"
    "userEnteredFormat.textFormat.foregroundColor,"
    "userEnteredFormat.textFormat.foregroundColorStyle,"
    "userEnteredFormat.textFormat.bold"
)
# 塗り直しは全日付列×全ASINを対象にするため数千セルになる。1リクエストに
# 詰めるとペイロードが膨らんで 400 が返るので分割して送る
FORMAT_CHUNK_SIZE = 500
# 確定したセルは numberFormat だけを書き、backgroundColor は cell 側に
# 無いので既定（色なし）に戻る。未確定は黄色を書き直す
SETTLEMENT_FORMAT_FIELDS = "userEnteredFormat(numberFormat,backgroundColor)"
GROSS_PROFIT_ESTIMATE_FORMAT = {
    "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8},
    "numberFormat": K_YEN_NUMBER_FORMAT,
}


def apply_column_formats(worksheet: Worksheet, col: int) -> None:
    worksheet.batch_format(
        [
            {"range": rowcol_to_a1(1, col), "format": DATE_LABEL_FORMAT},
            {"range": rowcol_to_a1(HEADER_ROW, col), "format": DATE_LABEL_FORMAT},
            {"range": rowcol_to_a1(FETCH_TIME_ROW, col), "format": TOTAL_AMOUNT_FORMAT},
            {"range": rowcol_to_a1(TOTAL_AMOUNT_ROW, col), "format": TOTAL_AMOUNT_FORMAT},
        ]
    )


def _date_serial(target_date: date) -> int:
    naive = datetime(target_date.year, target_date.month, target_date.day)
    return (naive - SHEETS_EPOCH).days


def _fetch_time_label() -> str:
    return datetime.now(JST).strftime("%H:%M")


class SalesSheet:
    def __init__(self, sales_worksheet: Worksheet) -> None:
        self._worksheet = sales_worksheet
        self._asin_list: list[str] = []
        self._asin_to_rows: dict[str, list[int]] = {}
        self._start_column: int = 0
        self._price_column: int = 0
        self._sales_column: int | None = None

    # write_sales_nums / write_prices below are @retry_on_transient_error; this read is
    # deliberately not. It runs before the hourly/realtime deadline budget starts
    # counting (see update_today_sales.py / update_realtime_sales.py), so a transient
    # failure here should fail fast via the gspread timeout rather than spend part of
    # that budget retrying with a 30s/60s backoff.
    def get_asin_list(self) -> list[str]:
        headers = self._worksheet.row_values(HEADER_ROW)
        self._start_column = self._find_column(headers, "目標販売数") + 1
        self._price_column = self._find_column(headers, "自社価格")
        values = self._worksheet.col_values(1)
        self._asin_list = []
        self._asin_to_rows = {}
        for i, v in enumerate(values):
            stripped = v.strip() if v else ""
            if len(stripped) != 10:
                continue
            if stripped not in self._asin_to_rows:
                self._asin_list.append(stripped)
                self._asin_to_rows[stripped] = []
            self._asin_to_rows[stripped].append(i + 1)
        return self._asin_list

    @retry_on_transient_error
    def write_sales_nums(
        self,
        asin_sales: dict[str, SalesInfo],
        target_date: date | None = None,
        include_total: bool = True,
    ) -> None:
        if target_date is None:
            target_date = (datetime.now(JST) - timedelta(days=1)).date()
        date_serial = _date_serial(target_date)
        col = self._resolve_column_for(date_serial)
        self._sales_column = col

        requests: list[dict] = []
        requests.append({"range": rowcol_to_a1(1, col), "values": [[date_serial]]})

        requests.append({"range": rowcol_to_a1(HEADER_ROW, col), "values": [[date_serial]]})

        total_amount = 0.0
        for asin in self._asin_list:
            if asin not in asin_sales:
                continue
            sales = asin_sales[asin]
            for row in self._asin_to_rows[asin]:
                if row > HEADER_ROW:
                    requests.append(
                        {"range": rowcol_to_a1(row, col), "values": [[sales.unit_count]]}
                    )
            total_amount += sales.total_sales_amount
        if include_total:
            # asin_sales may cover only a subset of ASINs (deadline cutoff, partial
            # fetch). Writing a total computed from a subset would silently understate
            # row 3 and contradict the individual cells. When the caller knows the
            # result is partial (include_total=False), leave row 3 as whatever the
            # previous run wrote rather than replace it with an incomplete sum.
            requests.append(
                {"range": rowcol_to_a1(TOTAL_AMOUNT_ROW, col), "values": [[total_amount]]}
            )

        # 当日列は毎時上書きされるため、いつ時点の数字かが分からないと読めない。
        # 日付列は毎日増えて位置が動くので、取得時刻は動かない「目標販売数」列の
        # 行2へ書く。過去日のバックフィルでは書かない（今日の更新時刻が壊れる）
        if target_date == datetime.now(JST).date():
            requests.append({
                "range": rowcol_to_a1(FETCH_TIME_ROW, self._start_column - 1),
                "values": [[f"取得 {_fetch_time_label()}"]],
            })

        self._worksheet.batch_update(requests, value_input_option="RAW")
        apply_column_formats(self._worksheet, col)

    def _resolve_column_for(self, date_serial: int) -> int:
        existing_column = self._find_serial_column(date_serial)
        if existing_column is not None:
            return existing_column
        self._insert_labeled_column(date_serial)
        return self._start_column

    def _insert_labeled_column(self, date_serial: int) -> None:
        label_column = [date_serial, *[""] * (HEADER_ROW - 2), date_serial]
        self._worksheet.insert_cols([label_column], self._start_column)

    def _find_serial_column(self, date_serial: int) -> int | None:
        header = self._worksheet.row_values(
            HEADER_ROW, value_render_option=ValueRenderOption.unformatted
        )
        for i, value in enumerate(header[self._start_column - 1:], start=self._start_column):
            if value == date_serial:
                return i
        return None

    def get_selling_prices(self) -> dict[str, float]:
        if not self._asin_list:
            return {}
        last_row = max(self._last_row_of(asin) for asin in self._asin_list)
        start_cell = rowcol_to_a1(1, self._price_column)
        end_cell = rowcol_to_a1(last_row, self._price_column)
        price_range = f"{start_cell}:{end_cell}"
        price_values = self._worksheet.get(price_range)
        result: dict[str, float] = {}
        for asin in self._asin_list:
            row = self._asin_to_rows[asin][0]
            if row - 1 < len(price_values):
                cell_value = price_values[row - 1][0] if price_values[row - 1] else ""
                if cell_value:
                    cleaned = str(cell_value).replace("¥", "").replace(",", "").strip()
                    if cleaned:
                        result[asin] = float(cleaned)
        return result

    def _last_row_of(self, asin: str) -> int:
        return self._asin_to_rows[asin][-1]

    @staticmethod
    def _find_column(headers: list[str], name: str) -> int:
        for i, value in enumerate(headers):
            if value.strip() == name:
                return i + 1
        raise ValueError(f"ヘッダーに '{name}' が見つかりません")

    @retry_on_transient_error
    def write_prices(self, prices: dict[str, float]) -> None:
        targets = [
            (asin, row)
            for asin in prices
            if asin in self._asin_to_rows
            for row in self._asin_to_rows[asin]
            if row > HEADER_ROW
        ]
        if self._sales_column is None:
            raise RuntimeError(
                "write_prices は write_sales_nums で対象列を解決した後にしか呼び出せません"
            )
        if not targets:
            return
        col = self._sales_column
        previous_prices = self._read_previous_prices(col + 1, max(row for _, row in targets))

        requests: list[dict] = []
        notes: dict[str, str] = {}
        written_cells: list[str] = []
        cheaper: list[str] = []
        pricier: list[str] = []
        for asin, row in targets:
            price = prices[asin]
            requests.append(
                {"range": rowcol_to_a1(row, self._price_column), "values": [[price]]}
            )
            cell = rowcol_to_a1(row, col)
            notes[cell] = str(price)
            written_cells.append(cell)
            previous = previous_prices.get(row)
            if previous is None:
                continue
            if price < previous:
                cheaper.append(cell)
            elif price > previous:
                pricier.append(cell)

        self._worksheet.batch_update(requests, value_input_option="RAW")
        self._worksheet.update_notes(notes)
        self._reset_price_change_style(written_cells)
        if cheaper:
            self._worksheet.format(cheaper, CHEAPER_FORMAT)
        if pricier:
            self._worksheet.format(pricier, PRICIER_FORMAT)

    # 価格は書き込み当時に売上個数セルのノートへ残してある。過去の列も
    # そのノートだけで塗り分けを再現できる（当時の価格を取り直す必要がない）
    def classify_price_changes(self) -> PriceChangeCells:
        return classify_from_notes(
            self._worksheet.get_notes(),
            self._asin_rows(),
            read_date_columns(self._worksheet),
        )

    # 変化なしのセルは塗らないだけで、既にある背景は消さない。当日列を毎回
    # 書き直す write_prices と違い、過去列は手で色を付けている可能性がある
    @retry_on_transient_error
    def recolor_price_changes(self) -> PriceChangeCells:
        cells = self.classify_price_changes()
        self._reset_price_change_style(cells.cheaper + cells.pricier)
        self._apply_style(cells.cheaper, CHEAPER_FORMAT)
        self._apply_style(cells.pricier, PRICIER_FORMAT)
        return cells

    def _asin_rows(self) -> list[int]:
        return [
            row
            for asin in self._asin_list
            for row in self._asin_to_rows[asin]
            if row > HEADER_ROW
        ]

    def _apply_style(self, cells: list[str], cell_format: dict) -> None:
        for chunk in _in_chunks(cells):
            self._worksheet.format(chunk, cell_format)

    def _reset_price_change_style(self, cells: list[str]) -> None:
        sheet_id = self._worksheet.id
        for chunk in _in_chunks(cells):
            requests = [
                {
                    "repeatCell": {
                        "range": a1_range_to_grid_range(cell, sheet_id),
                        "fields": PRICE_CHANGE_STYLE_FIELDS,
                    }
                }
                for cell in chunk
            ]
            self._worksheet.spreadsheet.batch_update({"requests": requests})

    @retry_on_transient_error
    def write_gross_profit(
        self, profit_by_asin: dict[str, float | None], target_date: date
    ) -> GrossProfitWriteResult:
        if not profit_by_asin:
            return GrossProfitWriteResult()

        # ここで黙って 0 件を返してはいけない。launchd の失敗通知は終了コードでしか
        # 鳴らないため、書き込み0件で正常終了すると Slack にも daily note にも出ず、
        # セルが何週間も空のまま気づかれない（19時間ハングと同じ無音の失敗）。
        column = read_date_columns(self._worksheet).get(label_date_serial(target_date))
        if column is None:
            raise GrossProfitRowsNotFoundError(
                f"{target_date} の日付列が見つからないため粗利益を書き込めません"
            )

        rows_by_asin = self._gross_profit_rows()
        targets = [
            (asin, row)
            for asin, rows in rows_by_asin.items()
            if asin in profit_by_asin
            for row in rows
            if row > HEADER_ROW
        ]
        if not targets:
            raise GrossProfitRowsNotFoundError(
                f"「{GROSS_PROFIT_ROW_LABEL}」行が1件も見つかりません"
                f"（対象 {len(profit_by_asin)} ASIN）"
            )
        written_asins = {asin for asin, _ in targets}
        asins_without_row = tuple(sorted(set(profit_by_asin) - written_asins))

        # batch_update は渡した dict の "range" を in-place でシート名付きに書き換える
        # (例: "CS9" -> "'売上/日'!CS9")。format() はシート名付きの範囲を受け付けないため、
        # batch_update に渡す前に書式対象のセルを別のリストへ保持しておく
        # (write_prices の written_cells と同じ回避)。
        written_cells = [rowcol_to_a1(row, column) for _, row in targets]
        requests = [
            {"range": cell, "values": [[_cell_value(profit_by_asin[asin])]]}
            for cell, (asin, _) in zip(written_cells, targets)
        ]
        estimated_cells = [
            cell
            for cell, (asin, _) in zip(written_cells, targets)
            if profit_by_asin[asin] is not None
        ]
        self._worksheet.batch_update(requests, value_input_option="RAW")
        if estimated_cells:
            self._worksheet.format(estimated_cells, GROSS_PROFIT_ESTIMATE_FORMAT)
        # 列が作られた直後は営業利益の数式が無い。粗利益を書くたびに入れ直す
        # （同じ数式なので何度書いても同じ）
        self.write_operating_profit_formulas([column])
        self.write_operating_profit_totals([column])
        return GrossProfitWriteResult(
            cells_written=len(requests), asins_without_row=asins_without_row
        )

    @retry_on_transient_error
    def write_actual_gross_profit(
        self, cells_by_date: dict[date, list[ActualProfitCell]]
    ) -> ActualProfitWriteResult:
        columns = read_date_columns(self._worksheet)
        rows_by_asin = self._gross_profit_rows()

        requests: list[dict] = []
        notes: dict[str, str] = {}
        settled_cells: list[str] = []
        written_columns: set[int] = set()
        skipped_dates: list[str] = []
        missing_asins: set[str] = set()

        for target_date, cells in cells_by_date.items():
            column = columns.get(label_date_serial(target_date))
            if column is None:
                skipped_dates.append(target_date.isoformat())
                continue
            for cell in cells:
                rows = [row for row in rows_by_asin.get(cell.asin, []) if row > HEADER_ROW]
                if not rows:
                    missing_asins.add(cell.asin)
                    continue
                written_columns.add(column)
                for row in rows:
                    a1 = rowcol_to_a1(row, column)
                    requests.append({"range": a1, "values": [[cell.profit]]})
                    notes[a1] = _estimate_note(cell)
                    if cell.fully_settled:
                        settled_cells.append(a1)

        if requests:
            # batch_update は渡した dict の "range" を in-place で書き換えるため、
            # ノートと書式の対象は先に別のリストへ控えてある
            all_cells = [request["range"] for request in requests]
            self._worksheet.batch_update(requests, value_input_option="RAW")
            self._worksheet.update_notes(notes)
            self._apply_settlement_formats(all_cells, set(settled_cells))
            self.write_operating_profit_formulas(sorted(written_columns))
            self.write_operating_profit_totals(sorted(written_columns))
        return ActualProfitWriteResult(
            cells_written=len(requests),
            cells_cleared=len(settled_cells),
            skipped_dates=tuple(skipped_dates),
            asins_without_row=tuple(sorted(missing_asins)),
        )

    def _apply_settlement_formats(self, cells: list[str], settled: set[str]) -> None:
        # 見積を書くのは当日・前日だけなので、それより古いセルは一度も黄色にも
        # K書式にもなっていない。ここで全セルに付け直さないと色分けが機能しない
        # （実シートで白い未確定セルと #,##0 のままのセルが出た）
        sheet_id = self._worksheet.id
        requests = [
            {
                "repeatCell": {
                    "range": a1_range_to_grid_range(cell, sheet_id),
                    "cell": {
                        "userEnteredFormat": {"numberFormat": K_YEN_NUMBER_FORMAT}
                        if cell in settled
                        else GROSS_PROFIT_ESTIMATE_FORMAT
                    },
                    "fields": SETTLEMENT_FORMAT_FIELDS,
                }
            }
            for cell in cells
        ]
        self._worksheet.spreadsheet.batch_update({"requests": requests})

    @retry_on_transient_error
    def write_operating_profit_formulas(self, columns: list[int]) -> int:
        # 営業利益は値ではなく数式で持つ。粗利益と広告費のどちらが後から更新
        # されても追従し、書き込む順序に依存しない。粗利益が空の日は空にする
        # （0 と書くと「利益ゼロ」と見分けがつかない）
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = find_label_column(headers, PRODUCT_NAME_HEADER)
        asin_values = self._worksheet.col_values(ASIN_COLUMN)
        name_values = self._worksheet.col_values(name_column)
        operating_rows = bind_label_rows(asin_values, name_values, OPERATING_PROFIT_ROW_LABEL)
        gross_rows = bind_label_rows(asin_values, name_values, GROSS_PROFIT_ROW_LABEL)
        cost_rows = bind_label_rows(asin_values, name_values, AD_COST_ROW_LABEL)

        requests = [
            {
                "range": rowcol_to_a1(row, column),
                "values": [[_operating_profit_formula(gross, cost, column)]],
            }
            for asin, rows in operating_rows.items()
            for row, gross, cost in zip(
                rows, gross_rows.get(asin, []), cost_rows.get(asin, [])
            )
            if row > HEADER_ROW
            for column in columns
        ]
        if not requests:
            return 0
        cells = [request["range"] for request in requests]
        self._worksheet.batch_update(requests, value_input_option="USER_ENTERED")
        self._apply_operating_profit_format(cells)
        return len(requests)

    def _apply_operating_profit_format(self, cells: list[str]) -> None:
        sheet_id = self._worksheet.id
        requests = [
            {
                "repeatCell": {
                    "range": a1_range_to_grid_range(cell, sheet_id),
                    "cell": {"userEnteredFormat": {"numberFormat": K_YEN_NUMBER_FORMAT}},
                    "fields": "userEnteredFormat.numberFormat",
                }
            }
            for cell in cells
        ]
        self._worksheet.spreadsheet.batch_update({"requests": requests})

    @retry_on_transient_error
    def write_operating_profit_totals(self, columns: list[int]) -> int:
        # 行ごとに合計するのではなく SUMIF で商品名列を引く。商品が増減しても
        # 数式を書き直さなくて済む
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = find_label_column(headers, PRODUCT_NAME_HEADER)
        name_letter = _column_letter(name_column)
        requests = [
            {
                "range": rowcol_to_a1(FETCH_TIME_ROW, column),
                "values": [[_operating_profit_total_formula(name_letter, column)]],
            }
            for column in columns
        ]
        if not requests:
            return 0
        cells = [request["range"] for request in requests]
        self._worksheet.batch_update(requests, value_input_option="USER_ENTERED")
        self._worksheet.format(cells, TOTAL_AMOUNT_FORMAT)
        return len(requests)

    def _gross_profit_rows(self) -> dict[str, list[int]]:
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = find_label_column(headers, PRODUCT_NAME_HEADER)
        asin_values = self._worksheet.col_values(ASIN_COLUMN)
        name_values = self._worksheet.col_values(name_column)
        return bind_label_rows(asin_values, name_values, GROSS_PROFIT_ROW_LABEL)

    def _read_previous_prices(self, col: int, last_row: int) -> dict[int, float]:
        cell_range = f"{rowcol_to_a1(1, col)}:{rowcol_to_a1(last_row, col)}"
        recorded_notes = self._worksheet.get_notes(grid_range=cell_range)
        result: dict[int, float] = {}
        for index, row_notes in enumerate(recorded_notes):
            raw = row_notes[0] if row_notes else ""
            if not raw:
                continue
            try:
                result[index + 1] = float(str(raw).replace(",", "").strip())
            except ValueError:
                continue
        return result


def _in_chunks(cells: list[str], size: int = FORMAT_CHUNK_SIZE) -> list[list[str]]:
    return [cells[i:i + size] for i in range(0, len(cells), size)]


def _estimate_note(cell: ActualProfitCell) -> str:
    return f"見積 {cell.estimate:,.0f} / 実測 {cell.profit:,.0f}"


def _cell_value(profit: float | None) -> float | str:
    return "" if profit is None else profit


def _operating_profit_formula(gross_row: int, cost_row: int, column: int) -> str:
    gross = rowcol_to_a1(gross_row, column)
    cost = rowcol_to_a1(cost_row, column)
    return f'=IF({gross}="","",{gross}-N({cost}))'


def _column_letter(column: int) -> str:
    letters = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _operating_profit_total_formula(name_letter: str, column: int) -> str:
    target = _column_letter(column)
    first = HEADER_ROW + 1
    return (
        f'=SUMIF(${name_letter}${first}:${name_letter},"{OPERATING_PROFIT_ROW_LABEL}",'
        f"{target}${first}:{target})"
    )
