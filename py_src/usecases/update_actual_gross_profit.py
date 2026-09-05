from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from py_src.domain.value_objects.actual_profit_cell import ActualProfitWriteResult
from py_src.domain.value_objects.gross_profit_write_result import (
    GrossProfitRowsNotFoundError,
)
from py_src.usecases.settle_gross_profit import (
    aggregate_settled,
    build_fee_gaps,
    build_profit_cells,
)

JST = timezone(timedelta(hours=9))
WINDOW_DAYS = 14
# SP-API は PostedBefore が「リクエストの2分前」より新しいと 400 を返す。
# 実際に now ちょうどで落ちたので余裕を持たせる
FINANCES_POSTED_BEFORE_MARGIN = timedelta(minutes=5)


class EmptyFinancesResultError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActualGrossProfitResult:
    write_result: ActualProfitWriteResult = field(default_factory=ActualProfitWriteResult)
    fee_gap_count: int = 0
    unknown_sku_count: int = 0


class UpdateActualGrossProfitUseCase:
    def __init__(
        self,
        sales_sheet: object,
        sales_repository: object,
        orders_repository: object,
        finances_repository: object,
        index_reader: object,
        fee_gap_sheet: object,
    ) -> None:
        self._sheet = sales_sheet
        self._sales_repo = sales_repository
        self._orders_repo = orders_repository
        self._finances_repo = finances_repository
        self._index_reader = index_reader
        self._fee_gap_sheet = fee_gap_sheet

    def execute(self) -> ActualGrossProfitResult:
        now = datetime.now(JST)
        start, end = self._window(now.date())
        # 手数料は注文より後に計上されるので、窓の開始から直近までを取る
        records = self._finances_repo.get_finance_records(
            _date_to_utc_iso(start), _instant_to_utc_iso(now - FINANCES_POSTED_BEFORE_MARGIN)
        )
        # 取得できていないだけの状態で見積を上書きしてはいけない。0件で正常終了
        # すると launchd の失敗通知が鳴らず、誰も気づけない
        if not records:
            raise EmptyFinancesResultError(
                f"{start}〜{end} の実測が1件も取得できませんでした"
            )

        index = self._index_reader.read()
        # 注文日は Reports API から取る。getOrders は 1分あたり1リクエストで、
        # 14日分の約100ページに100分かかる（実 API の検証が 429 で落ちた）
        purchase_dates = self._orders_repo.get_purchase_dates(start, end)
        settled, unknown_sku_count = aggregate_settled(
            records, purchase_dates, index.sku_to_asin
        )
        sales_by_asin = self._sales_repo.get_sales_by_date(
            self._sheet.get_asin_list(), _to_jst_iso(start), _to_jst_iso(end)
        )
        cells_by_date = build_profit_cells(sales_by_asin, settled, index.costs)
        write_result = self._sheet.write_actual_gross_profit(cells_by_date)
        # 書くものがあるのに1セルも書けなかったのは、ラベル行か日付列の異常。
        # 0件で正常終了すると launchd の失敗通知が鳴らない
        if cells_by_date and write_result.cells_written == 0:
            raise GrossProfitRowsNotFoundError(
                "粗利益を1セルも書き込めませんでした"
                f"（対象 {sum(len(cells) for cells in cells_by_date.values())} セル、"
                f"スキップした日付 {len(write_result.skipped_dates)}）"
            )

        gaps = build_fee_gaps(settled, index.costs)
        self._fee_gap_sheet.write(gaps, index.names, now)
        return ActualGrossProfitResult(
            write_result=write_result,
            fee_gap_count=len(gaps),
            unknown_sku_count=unknown_sku_count,
        )

    @staticmethod
    def _window(today: date) -> tuple[date, date]:
        # 当日は注文が確定しておらず、実測もほとんど付かない。前日までを対象にする
        return today - timedelta(days=WINDOW_DAYS), today


def _to_jst_iso(target: date) -> str:
    return datetime(target.year, target.month, target.day, tzinfo=JST).isoformat()


def _date_to_utc_iso(target: date) -> str:
    return _instant_to_utc_iso(datetime(target.year, target.month, target.day, tzinfo=JST))


def _instant_to_utc_iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
