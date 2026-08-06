import os
import logging
from datetime import datetime

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None


class GoogleSheetHandler(logging.Handler):
    """A logging handler that appends log records to a Google Sheets worksheet named 'logs'.

    It attempts to create/initialize the worksheet if missing and is resilient to failures
    (it will swallow errors to avoid breaking the application when logging to Sheets fails).
    """

    def __init__(self, spreadsheet_id=None, service_account_file=None, scopes=None, worksheet_name="logs"):
        super().__init__()
        self.enabled = False
        self.spreadsheet_id = spreadsheet_id or os.getenv("SPREADSHEET_ID")
        self.service_account_file = service_account_file or os.path.join(os.path.dirname(__file__), "service_account.json")
        self.scopes = scopes or ["https://www.googleapis.com/auth/spreadsheets"]
        self.worksheet_name = worksheet_name
        self.client = None
        self.worksheet = None

        if gspread is None:
            # gspread not installed / import failed
            return

        if not self.spreadsheet_id or not os.path.exists(self.service_account_file):
            # Missing configuration or service account file
            return

        try:
            creds = Credentials.from_service_account_file(self.service_account_file, scopes=self.scopes)
            self.client = gspread.authorize(creds)
            sh = self.client.open_by_key(self.spreadsheet_id)

            # Ensure worksheet exists
            try:
                self.worksheet = sh.worksheet(self.worksheet_name)
            except gspread.WorksheetNotFound:
                # Create a new worksheet with some default size
                self.worksheet = sh.add_worksheet(title=self.worksheet_name, rows=1000, cols=10)

            # Ensure header row exists
            try:
                values = self.worksheet.get_all_values()
                if not values or (len(values) == 1 and all(not cell for cell in values[0])):
                    header = ["timestamp", "level", "logger", "message", "module", "funcName", "lineno"]
                    self.worksheet.insert_row(header, index=1)

            except Exception:
                # Non-fatal: continue even if header check fails
                pass

            self.enabled = True
        except Exception:
            # Any failure in setup should not crash the app
            self.enabled = False

    def emit(self, record: logging.LogRecord):
        if not self.enabled:
            return

        try:
            timestamp = datetime.utcfromtimestamp(record.created).isoformat() + "Z"
            row = [
                timestamp,
                record.levelname,
                record.name,
                self.format(record),
                getattr(record, "module", ""),
                getattr(record, "funcName", ""),
                getattr(record, "lineno", ""),
            ]
            # Append row to sheet
            # Use append_row with value_input_option="USER_ENTERED"
            try:
                self.worksheet.append_row(row, value_input_option="USER_ENTERED")
            except Exception:
                # On append failure, try reconnecting once
                try:
                    creds = Credentials.from_service_account_file(self.service_account_file, scopes=self.scopes)
                    self.client = gspread.authorize(creds)
                    sh = self.client.open_by_key(self.spreadsheet_id)
                    try:
                        self.worksheet = sh.worksheet(self.worksheet_name)
                    except gspread.WorksheetNotFound:
                        self.worksheet = sh.add_worksheet(title=self.worksheet_name, rows=1000, cols=10)
                    self.worksheet.append_row(row, value_input_option="USER_ENTERED")
                except Exception:
                    # Give up silently to avoid breaking the main app
                    pass
        except Exception:
            # Ensure no exception propogates from logging handler
            pass


# Helper to write a single run summary row (one row per pipeline run)
def write_run_summary(run_time, status, stage, rows_extracted=None, rows_uploaded=None, duration_sec=None, message=None, spreadsheet_id=None, service_account_file=None, scopes=None, worksheet_name="logs"):
    """Append a single run summary row to the specified worksheet.

    Columns: Run Time, Status, Stage, Rows Extracted, Rows Uploaded, Duration (sec), Message

    All errors are swallowed to avoid impacting the main pipeline run.
    """
    if gspread is None:
        return

    spreadsheet_id = spreadsheet_id or os.getenv("SPREADSHEET_ID")
    service_account_file = service_account_file or os.path.join(os.path.dirname(__file__), "service_account.json")
    scopes = scopes or ["https://www.googleapis.com/auth/spreadsheets"]

    if not spreadsheet_id or not os.path.exists(service_account_file):
        return

    try:
        creds = Credentials.from_service_account_file(service_account_file, scopes=scopes)
        client = gspread.authorize(creds)
        sh = client.open_by_key(spreadsheet_id)

        # Ensure worksheet exists
        try:
            worksheet = sh.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=worksheet_name, rows=1000, cols=10)

        # Ensure header
        header = ["Run Time", "Status", "Stage", "Rows Extracted", "Rows Uploaded", "Duration (sec)", "Message"]
        try:
            values = worksheet.get_all_values()
            if not values or values[0] != header:
                # If no header or different header, replace first row with expected header
                # Use update to set first row
                worksheet.update(range_name="A1", values=[header], value_input_option="USER_ENTERED")
        except Exception:
            # non-fatal
            pass

        # Format values
        if isinstance(run_time, (int, float)):
            run_time_str = datetime.utcfromtimestamp(run_time).strftime("%Y-%m-%d %H:%M:%S")
        elif hasattr(run_time, "strftime"):
            run_time_str = run_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            run_time_str = str(run_time)

        row = [
            run_time_str,
            status or "",
            stage or "",
            "" if rows_extracted is None else int(rows_extracted),
            "" if rows_uploaded is None else int(rows_uploaded),
            "" if duration_sec is None else float(round(duration_sec, 2)),
            message or "",
        ]

        worksheet.append_row(row, value_input_option="USER_ENTERED")
    except Exception:
        # Swallow any errors
        return
