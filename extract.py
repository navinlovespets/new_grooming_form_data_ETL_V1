import pandas as pd
from config import get_analytics_engine, get_st_engine, setup_logging

logger = setup_logging()


def fetch_appointments():
    """Load grooming appointments for the given date range."""
    logger.info("Fetching appointments from analytics database...")
    query = """
        SELECT *
        FROM clinic_appointments
        WHERE appointment_type = 'Grooming'
          AND no_show = 0
          AND DATE(appointment_date) BETWEEN '2026-08-01' AND '2026-08-05'
    """
    try:
        engine = get_analytics_engine()
        df = pd.read_sql(query, engine)
        logger.info(f"Fetched {len(df):,} appointments.")
        return df
    except Exception as e:
        logger.error(f"Failed to fetch appointments: {e}")
        raise


def fetch_webhook_logs():
    """Load webhook logs for CREATE_INVOICE."""
    logger.info("Fetching webhook logs from staging database...")
    query = """
        SELECT appointmentId, request
        FROM VetPMS.webhook_logs
        WHERE webhookName = 'CREATE_INVOICE'
    """
    try:
        engine = get_st_engine()
        df = pd.read_sql(query, engine)
        logger.info(f"Fetched {len(df):,} webhook logs.")
        return df
    except Exception as e:
        logger.error(f"Failed to fetch webhook logs: {e}")
        raise
