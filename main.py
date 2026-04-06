import os

from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import gspread

from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository
from py_src.infrastructure.api.sp_api_price_repository import SpApiPriceRepository
from py_src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet
from py_src.infrastructure.sheets.sales_sheet import SalesSheet
from py_src.usecases.update_realtime_sales import UpdateRealtimeSalesUseCase
from py_src.usecases.update_daily_sales import UpdateDailySalesUseCase


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


def _open_spreadsheet() -> gspread.Spreadsheet:
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(spreadsheet_id)


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


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "daily":
        update_daily_sales()
    else:
        main()
