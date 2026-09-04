from __future__ import annotations
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# (connect_timeout_seconds, read_timeout_seconds) applied to every request gspread's
# shared HTTPClient makes (open_by_key, worksheet(), row/col reads, batch_update, ...).
# Without this, a Sheets API call that accepts the connection but never responds hangs
# forever the same way the un-timed-out SP-API calls did in the 19h42m incident — and
# it would hang *before* any per-usecase deadline ever gets a chance to start counting,
# since spreadsheet access happens ahead of that.
GOOGLE_SHEETS_TIMEOUT_SECONDS: tuple[float, float] = (10.0, 30.0)

GOOGLE_SHEETS_SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


def open_spreadsheet(credentials_file: str, spreadsheet_id: str) -> gspread.Spreadsheet:
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, GOOGLE_SHEETS_SCOPE)
    client = gspread.authorize(creds)
    client.set_timeout(GOOGLE_SHEETS_TIMEOUT_SECONDS)
    return client.open_by_key(spreadsheet_id)
