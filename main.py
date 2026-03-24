import os

from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import gspread

from py_src.infrastructure.api.orders_repository import OrdersRepository
from py_src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet
from py_src.usecases.update_realtime_sales import UpdateRealtimeSalesUseCase


def main() -> None:
    load_dotenv()

    repository = OrdersRepository(
        client_id=os.getenv("API_KEY", ""),
        client_secret=os.getenv("API_SECRET", ""),
        refresh_token=os.getenv("REFRESH_TOKEN", ""),
    )

    worksheet = _open_worksheet()
    sheet = RealtimeSalesSheet(worksheet=worksheet)

    usecase = UpdateRealtimeSalesUseCase(sheet=sheet, repository=repository)
    usecase.execute()


def _open_worksheet() -> gspread.Worksheet:
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    sheet_name = os.getenv("SHEET_NAME", "売上/今")

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(spreadsheet_id)
    return spreadsheet.worksheet(sheet_name)


if __name__ == "__main__":
    main()
