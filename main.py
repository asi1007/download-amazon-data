import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from amazon_api import spapi_credentials
from dotenv import load_dotenv
import gspread

from sales_data.domain.value_objects.gross_profit_write_result import GrossProfitWriteResult
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.sp_api_catalog import SpApiCatalog
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository
from py_src.infrastructure.api.sp_api_price_repository import SpApiPriceRepository
from py_src.infrastructure.api.sp_api_inventory_repository import SpApiInventoryRepository
from py_src.infrastructure.api.finances_repository import FinancesRepository
from py_src.infrastructure.api.orders_report_repository import OrdersReportRepository
from py_src.infrastructure.api.ads_credentials_loader import load_ads_credentials
from py_src.infrastructure.api.ads_units_repository import AdsUnitsRepository
from py_src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet
from sales_data.infrastructure.sheets.repository import SheetsSalesRepository
from py_src.infrastructure.sheets.amazon_ad_sheet import AmazonAdSheet
from py_src.infrastructure.sheets.sales_data_sheet import SalesDataSheet
from py_src.infrastructure.sheets.inventory_sheet import InventorySheet
from sales_data.infrastructure.sheets.ad_sales_sheet import AdSalesSheet
from sales_data.infrastructure.sheets.unit_cost_reader import UnitCostReader
from sales_data.infrastructure.sheets.product_index_reader import ProductIndexReader
from py_src.infrastructure.sheets.fee_gap_sheet import FeeGapSheet
from sales_data.infrastructure.sheets.rank_sheet import RankSheet
from sales_data.infrastructure.sheets.gradient_rules import GradientRules
from sales_data.infrastructure.sheets.retry import retry_on_transient_error
from sales_data.infrastructure.sheets.row_groups import RowGroups
from sales_data.infrastructure.sheets.spreadsheet_client import open_spreadsheet
from py_src.usecases.update_realtime_sales import UpdateRealtimeSalesUseCase
from py_src.usecases.update_daily_sales import UpdateDailySalesUseCase
from py_src.usecases.update_today_sales import UpdateTodaySalesUseCase
from py_src.usecases.update_weekly_sales import UpdateWeeklySalesUseCase
from py_src.usecases.update_inventory_status import UpdateInventoryStatusUseCase
from py_src.usecases.update_ad_sales import UpdateAdSalesUseCase
from py_src.usecases.update_actual_gross_profit import UpdateActualGrossProfitUseCase
from py_src.usecases.update_category_ranks import UpdateCategoryRanksUseCase

ADS_ENV_PATH = Path(__file__).resolve().parents[1] / "dwld-ad-data" / ".env"


JST = timezone(timedelta(hours=9))


def main() -> None:
    load_dotenv()
    authenticator = _create_authenticator()
    sales_repository = SpApiSalesRepository(authenticator=authenticator)
    spreadsheet = _open_spreadsheet()

    realtime_ws = spreadsheet.worksheet("売上/今")
    realtime_sheet = RealtimeSalesSheet(worksheet=realtime_ws)

    sales_ws = spreadsheet.worksheet("売上/日")
    sales_sheet = SheetsSalesRepository(sales_worksheet=sales_ws)

    usecase = UpdateRealtimeSalesUseCase(
        realtime_sheet=realtime_sheet,
        sales_repository=sales_repository,
        sales_sheet=sales_sheet,
    )
    usecase.execute()


def _create_authenticator() -> SpApiAuthenticator:
    credentials = spapi_credentials()
    return SpApiAuthenticator(
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        refresh_token=credentials.refresh_token,
    )


@retry_on_transient_error
def _open_spreadsheet() -> gspread.Spreadsheet:
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    return open_spreadsheet(credentials_file, spreadsheet_id)


def update_daily_sales() -> None:
    load_dotenv()
    authenticator = _create_authenticator()
    sales_repository = SpApiSalesRepository(authenticator=authenticator)
    price_repository = SpApiPriceRepository(authenticator=authenticator)
    spreadsheet = _open_spreadsheet()
    sales_ws = spreadsheet.worksheet("売上/日")
    sales_sheet = SheetsSalesRepository(sales_worksheet=sales_ws)
    cost_reader = UnitCostReader(sales_ws)
    usecase = UpdateDailySalesUseCase(
        sales_sheet=sales_sheet,
        sales_repository=sales_repository,
        price_repository=price_repository,
        cost_reader=cost_reader,
    )
    _print_gross_profit_result(usecase.execute())
    # 個数の色は直近1ヶ月の中央値を白に置く。中央値は日々動くので、書いた
    # あとに掛け直さないと実行した日の中央値のまま古びる
    print(f"条件付き書式を {GradientRules(sales_ws).apply()} 件設定しました")
    # 人が中を見るために開いた行を閉じ直す。グループを作り直さないのは、
    # 新商品のグループ作成が漏れていたときにそれを隠さないため
    print(f"開いていた行グループを {RowGroups(sales_ws).collapse_expanded()} 件閉じました")


def update_today_sales() -> None:
    load_dotenv()
    authenticator = _create_authenticator()
    sales_repository = SpApiSalesRepository(authenticator=authenticator)
    spreadsheet = _open_spreadsheet()
    sales_ws = spreadsheet.worksheet("売上/日")
    sales_sheet = SheetsSalesRepository(sales_worksheet=sales_ws)
    cost_reader = UnitCostReader(sales_ws)
    usecase = UpdateTodaySalesUseCase(
        sales_sheet=sales_sheet,
        sales_repository=sales_repository,
        cost_reader=cost_reader,
    )
    _print_gross_profit_result(usecase.execute())


def _print_gross_profit_result(result: GrossProfitWriteResult) -> None:
    print(f"粗利益を {result.cells_written} セル書き込みました")
    if result.asins_without_row:
        print(
            f"粗利益の行が無い ASIN（{len(result.asins_without_row)}件）: "
            f"{', '.join(result.asins_without_row)}"
        )


def update_weekly_sales() -> None:
    load_dotenv()
    authenticator = _create_authenticator()
    sales_repository = SpApiSalesRepository(authenticator=authenticator)
    spreadsheet = _open_spreadsheet()
    sales_sheet = SheetsSalesRepository(sales_worksheet=spreadsheet.worksheet("売上/日"))
    ad_sheet = AmazonAdSheet(worksheet=spreadsheet.worksheet("Amazon広告"))
    sales_data_sheet = SalesDataSheet(worksheet=spreadsheet.worksheet("sales_data"))
    usecase = UpdateWeeklySalesUseCase(
        sales_sheet=sales_sheet,
        sales_repository=sales_repository,
        ad_sheet=ad_sheet,
        sales_data_sheet=sales_data_sheet,
    )
    usecase.execute()


def update_inventory_status() -> None:
    load_dotenv()
    authenticator = _create_authenticator()
    authenticator.authenticate()
    inventory_repository = SpApiInventoryRepository(authenticator=authenticator)
    price_repository = SpApiPriceRepository(authenticator=authenticator)
    spreadsheet = _open_spreadsheet()
    inventory_sheet = InventorySheet(worksheet=spreadsheet.worksheet("納品状況"))
    usecase = UpdateInventoryStatusUseCase(
        inventory_repository=inventory_repository,
        price_repository=price_repository,
        inventory_sheet=inventory_sheet,
    )
    count = usecase.execute()
    print(f"納品状況シートに {count} 件書き込みました")


def update_actual_gross_profit() -> None:
    load_dotenv()
    authenticator = _create_authenticator()
    spreadsheet = _open_spreadsheet()
    sales_ws = spreadsheet.worksheet("売上/日")
    usecase = UpdateActualGrossProfitUseCase(
        sales_sheet=SheetsSalesRepository(sales_worksheet=sales_ws),
        sales_repository=SpApiSalesRepository(authenticator=authenticator),
        orders_repository=OrdersReportRepository(authenticator=authenticator),
        finances_repository=FinancesRepository(authenticator=authenticator),
        index_reader=ProductIndexReader(sales_ws),
        fee_gap_sheet=FeeGapSheet(spreadsheet),
    )
    result = usecase.execute()
    written = result.write_result
    print(
        f"粗利益を実測で {written.cells_written} セル上書きし、"
        f"{written.cells_cleared} セルを確定（黄色を解除）しました"
    )
    print(f"手数料乖離シートに {result.fee_gap_count} 件書き込みました")
    if written.skipped_dates:
        print(
            f"日付列が無くスキップ（{len(written.skipped_dates)}日）: "
            f"{', '.join(written.skipped_dates)}"
        )
    if written.asins_without_row:
        print(
            f"粗利益の行が無い ASIN（{len(written.asins_without_row)}件）: "
            f"{', '.join(written.asins_without_row)}"
        )
    if result.unknown_sku_count:
        print(f"売上/日 に無い SKU を {result.unknown_sku_count} 件除外しました")


def update_ad_sales() -> None:
    load_dotenv()
    credentials = load_ads_credentials(ADS_ENV_PATH)
    ads_repository = AdsUnitsRepository(credentials=credentials)
    spreadsheet = _open_spreadsheet()
    ad_sheet = AdSalesSheet(worksheet=spreadsheet.worksheet("売上/日"))
    usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)
    result = usecase.execute()
    print(
        f"広告経由の売上個数を {result.unit_cells_written} セル、"
        f"広告費を {result.cost_cells_written} セル書き込みました"
    )
    if result.asins_without_cost_row:
        print(
            f"広告費の行が無い ASIN（{len(result.asins_without_cost_row)}件）: "
            f"{', '.join(result.asins_without_cost_row)}"
        )
    if result.skipped_dates:
        print(
            f"日付列が無くスキップ（{len(result.skipped_dates)}日）: "
            f"{', '.join(result.skipped_dates)}"
        )


def update_category_ranks() -> None:
    load_dotenv()
    day = _rank_target_date()
    authenticator = _create_authenticator()
    authenticator.authenticate()
    spreadsheet = _open_spreadsheet()
    usecase = UpdateCategoryRanksUseCase(
        sheet=RankSheet(worksheet=spreadsheet.worksheet("売上/日")),
        catalog=SpApiCatalog(authenticator=authenticator),
    )
    result = usecase.execute(day)
    print(f"{day} のカテゴリ順位を {result.cells_written} セル書き込みました")
    if result.label_updates:
        print(f"カテゴリ名を {result.label_updates} 行に入れました")
    if result.skipped_date:
        print(f"{day} の日付列が売上/日 に無いためスキップしました")
    if result.missing_rows:
        print(
            f"順位行が無い ASIN（{len(result.missing_rows)}件）: "
            f"{', '.join(result.missing_rows)}"
        )


def _rank_target_date() -> date:
    import sys

    if "--date" in sys.argv:
        return date.fromisoformat(sys.argv[sys.argv.index("--date") + 1])
    return datetime.now(JST).date()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "daily":
        update_daily_sales()
    elif len(sys.argv) > 1 and sys.argv[1] == "today":
        update_today_sales()
    elif len(sys.argv) > 1 and sys.argv[1] == "weekly":
        update_weekly_sales()
    elif len(sys.argv) > 1 and sys.argv[1] == "inventory":
        update_inventory_status()
    elif len(sys.argv) > 1 and sys.argv[1] == "ads":
        update_ad_sales()
    elif len(sys.argv) > 1 and sys.argv[1] == "finances":
        update_actual_gross_profit()
    elif len(sys.argv) > 1 and sys.argv[1] == "ranks":
        update_category_ranks()
    else:
        main()
