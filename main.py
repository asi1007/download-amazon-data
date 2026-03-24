import os

from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import gspread

from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.orders_repository import OrdersRepository
from py_src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet
from py_src.usecases.update_realtime_sales import UpdateRealtimeSalesUseCase


def main() -> None:
    load_dotenv()
    authenticator = _create_authenticator()
    repository = OrdersRepository(authenticator=authenticator)
    spreadsheet = _open_spreadsheet()
    sheet_name = os.getenv("SHEET_NAME", "売上/今")
    worksheet = spreadsheet.worksheet(sheet_name)
    sheet = RealtimeSalesSheet(worksheet=worksheet)
    usecase = UpdateRealtimeSalesUseCase(sheet=sheet, repository=repository)
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


if __name__ == "__main__":
    main()
