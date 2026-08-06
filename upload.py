import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1
from config import SPREADSHEET_ID, WORKSHEET_NAME, SERVICE_ACCOUNT_FILE, SCOPES, setup_logging

logger = setup_logging()

def upload_to_google_sheet(base_df):
    """Upload a DataFrame to Google Sheets, clearing and resizing the sheet.

    Returns the number of data rows uploaded (excluding header).
    """
    if base_df.empty:
        raise ValueError("No data available to upload.")

    logger.info("Authenticating with Google Sheets...")
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)

    # Prepare data
    upload_df = base_df.copy()

    # Convert datetime and timedelta columns to strings
    datetime_cols = upload_df.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns
    for col in datetime_cols:
        upload_df[col] = upload_df[col].dt.strftime("%Y-%m-%d")

    timedelta_cols = upload_df.select_dtypes(include=["timedelta64[ns]"]).columns
    for col in timedelta_cols:
        upload_df[col] = upload_df[col].astype(str)

    # Replace NaN with empty strings
    upload_df = upload_df.fillna("")

    # Convert all values to Python primitives
    def convert_value(val):
        if pd.isna(val):
            return ""
        if isinstance(val, (np.integer, np.floating, np.bool_)):
            return val.item()
        if isinstance(val, pd.Timestamp):
            return val.strftime("%Y-%m-%d")
        return str(val)

    # Use applymap for pandas <2.1, map for >=2.1
    try:
        upload_df = upload_df.applymap(convert_value)
    except AttributeError:
        upload_df = upload_df.map(convert_value)

    # Clear and resize sheet
    logger.info("Clearing and resizing the worksheet...")
    worksheet.clear()
    required_rows = len(upload_df) + 1000
    required_cols = len(upload_df.columns)
    worksheet.resize(rows=required_rows, cols=required_cols)

    # Build rows list
    rows = [upload_df.columns.tolist()] + upload_df.values.tolist()
    chunk_size = 1000

    # Upload header
    worksheet.update(range_name="A1", values=[rows[0]], value_input_option="USER_ENTERED")

    # Upload data in chunks
    data_rows = rows[1:]
    total_rows = len(data_rows)
    for start in range(0, total_rows, chunk_size):
        end = min(start + chunk_size, total_rows)
        chunk = data_rows[start:end]
        start_row = start + 2
        end_row = start_row + len(chunk) - 1
        range_name = f"A{start_row}:{rowcol_to_a1(end_row, required_cols)}"
        worksheet.update(
            range_name=range_name,
            values=chunk,
            value_input_option="USER_ENTERED",
        )
        logger.info(f"Uploaded {end:,}/{total_rows:,} rows")

    logger.info("Google Sheet updated successfully.")
    return total_rows
