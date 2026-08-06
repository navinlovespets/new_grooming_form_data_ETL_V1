import sys
from datetime import datetime
from config import setup_logging, SERVICE_ACCOUNT_FILE, SPREADSHEET_ID
from extract import fetch_appointments, fetch_webhook_logs
from transform import transform_data
from upload import upload_to_google_sheet
from gsheets_logger import write_run_summary


def main():
    # Setup logging
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("Starting Grooming Appointment Report Pipeline")
    logger.info("=" * 60)

    start_time = datetime.now()
    rows_extracted = None
    rows_uploaded = None
    stage = "Init"
    status = "FAILED"
    message = ""

    try:
        # Extract
        stage = "Extract"
        appointments = fetch_appointments()
        webhooks = fetch_webhook_logs()
        rows_extracted = len(appointments) if appointments is not None else 0

        # Transform
        stage = "Transform"
        final_df = transform_data(appointments, webhooks)

        # Upload
        stage = "Upload"
        rows_uploaded = upload_to_google_sheet(final_df)

        stage = "Completed"
        status = "SUCCESS"
        message = "ETL Completed Successfully"

        logger.info("Pipeline completed successfully.")
        return 0
    except Exception as exc:
        # Capture exception info for run summary
        logger.exception("Pipeline failed with an exception.")
        message = f"{exc.__class__.__name__}: {str(exc)}"
        status = "FAILED"
        # do not re-raise; we will record the failure in the logs sheet below
        return 1
    finally:
        # Write a single run summary row to the logs worksheet (best-effort)
        try:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            run_time = start_time
            # Only call write_run_summary if spreadsheet id and service account available
            write_run_summary(
                run_time=run_time,
                status=status,
                stage=stage,
                rows_extracted=rows_extracted,
                rows_uploaded=rows_uploaded,
                duration_sec=duration,
                message=message,
                spreadsheet_id=SPREADSHEET_ID,
                service_account_file=SERVICE_ACCOUNT_FILE,
                worksheet_name="logs",
            )
        except Exception:
            # swallow any errors from logging summary
            pass


if __name__ == "__main__":
    sys.exit(main())
