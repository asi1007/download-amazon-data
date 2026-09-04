import os
from pathlib import Path

from dotenv import load_dotenv
import gspread

from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository
from py_src.infrastructure.api.sp_api_price_repository import SpApiPriceRepository
from py_src.infrastructure.api.sp_api_inventory_repository import SpApiInventoryRepository
from py_src.infrastructure.api.ads_credentials_loader import load_ads_credentials
from py_src.infrastructure.api.ads_units_repository import AdsUnitsRepository
from py_src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet
from py_src.infrastructure.sheets.sales_sheet import SalesSheet
from py_src.infrastructure.sheets.amazon_ad_sheet import AmazonAdSheet
from py_src.infrastructure.sheets.sales_data_sheet import SalesDataSheet
from py_src.infrastructure.sheets.inventory_sheet import InventorySheet
from py_src.infrastructure.sheets.ad_sales_sheet import AdSalesSheet
from py_src.infrastructure.sheets.retry import retry_on_transient_error
from py_src.infrastructure.sheets.spreadsheet_client import open_spreadsheet
from py_src.usecases.update_realtime_sales import UpdateRealtimeSalesUseCase
from py_src.usecases.update_daily_sales import UpdateDailySalesUseCase
from py_src.usecases.update_today_sales import UpdateTodaySalesUseCase
from py_src.usecases.update_weekly_sales import UpdateWeeklySalesUseCase
from py_src.usecases.update_inventory_status import UpdateInventoryStatusUseCase
from py_src.usecases.update_ad_sales import UpdateAdSalesUseCase

ADS_ENV_PATH = Path(__file__).resolve().parents[1] / "dwld-ad-data" / ".env"


def main() -> None:
    load_dotenv()
    authenticator = _create_authenticator()
    sales_repository = SpApiSalesRepository(authenticator=authenticator)
    spreadsheet = _open_spreadsheet()

    realtime_ws = spreadsheet.worksheet("売上/今")
    realtime_sheet = RealtimeSalesSheet(worksheet=realtime_ws)

    sales_ws = spreadsheet.worksheet("売上/日")
    sales_sheet = SalesSheet(sales_worksheet=sales_ws)

    usecase = UpdateRealtimeSalesUseCase(
        realtime_sheet=realtime_sheet,
        sales_repository=sales_repository,
        sales_sheet=sales_sheet,
    )
    usecase.execute()


def _create_authenticator() -> SpApiAuthenticator:
    return SpApiAuthenticator(
        client_id=os.getenv("API_KEY", ""),
        client_secret=os.getenv("API_SECRET", ""),
        refresh_token=os.getenv("REFRESH_TOKEN", ""),
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
    sales_sheet = SalesSheet(sales_worksheet=sales_ws)
    usecase = UpdateDailySalesUseCase(
        sales_sheet=sales_sheet,
        sales_repository=sales_repository,
        price_repository=price_repository,
    )
    usecase.execute()


def update_today_sales() -> None:
    load_dotenv()
    authenticator = _create_authenticator()
    sales_repository = SpApiSalesRepository(authenticator=authenticator)
    spreadsheet = _open_spreadsheet()
    sales_ws = spreadsheet.worksheet("売上/日")
    sales_sheet = SalesSheet(sales_worksheet=sales_ws)
    usecase = UpdateTodaySalesUseCase(
        sales_sheet=sales_sheet,
        sales_repository=sales_repository,
    )
    usecase.execute()


def update_weekly_sales() -> None:
    load_dotenv()
    authenticator = _create_authenticator()
    sales_repository = SpApiSalesRepository(authenticator=authenticator)
    spreadsheet = _open_spreadsheet()
    sales_sheet = SalesSheet(sales_worksheet=spreadsheet.worksheet("売上/日"))
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


def update_ad_sales() -> None:
    load_dotenv()
    credentials = load_ads_credentials(ADS_ENV_PATH)
    ads_repository = AdsUnitsRepository(credentials=credentials)
    spreadsheet = _open_spreadsheet()
    ad_sheet = AdSalesSheet(worksheet=spreadsheet.worksheet("売上/日"))
    usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)
    result = usecase.execute()
    print(f"広告経由の売上個数を {result.cells_written} セル書き込みました")
    if result.skipped_dates:
        print(
            f"日付列が無くスキップ（{len(result.skipped_dates)}日）: "
            f"{', '.join(result.skipped_dates)}"
        )


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
    else:
        main()
