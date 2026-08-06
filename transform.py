import json
import pandas as pd
from config import setup_logging

logger = setup_logging()

def extract_pre_grooming(request):
    """
    Parse the 'request' JSON and extract the first pre‑grooming form.
    Returns a Series with form_name, form_content, form_link.
    """
    if not isinstance(request, str) or not request.strip():
        return pd.Series({"form_name": None, "form_content": None, "form_link": None})

    try:
        data = json.loads(request)
        service_forms = data.get("invoice", {}).get("service_forms", [])

        for form in service_forms:
            form_name = form.get("form_name", "").strip().lower()
            if form_name.startswith("pre grooming") or form_name == "grooming admission & care form":
                return pd.Series({
                    "form_name": form.get("form_name"),
                    "form_content": form.get("content"),
                    "form_link": form.get("form_link"),
                })
    except Exception as e:
        logger.warning(f"Error parsing request: {e}")

    return pd.Series({"form_name": None, "form_content": None, "form_link": None})

def transform_data(appointments_df, webhook_df):
    """
    Merge, extract forms, add computed columns, and select final output.
    Returns the final DataFrame.
    """
    logger.info("Starting data transformation...")

    # 1. Extract form details from webhook logs
    logger.info("Extracting pre‑grooming forms from webhook logs...")
    webhook_df[["form_name", "form_content", "form_link"]] = (
        webhook_df["request"].apply(extract_pre_grooming)
    )
    webhook_df = webhook_df[["appointmentId", "form_name", "form_content", "form_link"]]
    webhook_df = webhook_df.drop_duplicates(subset="appointmentId", keep="first")
    logger.info(f"Webhook logs after deduplication: {len(webhook_df):,}")

    # 2. Merge
    logger.info("Merging appointments with webhook data...")
    merged = appointments_df.merge(
        webhook_df,
        left_on="appointment_id",
        right_on="appointmentId",
        how="left"
    )
    merged.drop(columns=["appointmentId"], inplace=True, errors="ignore")

    # 3. Additional columns
    merged["appointment_date"] = pd.to_datetime(merged["appointment_date"])
    merged["month"] = merged["appointment_date"].dt.strftime("%b")

    # 4. Select final columns
    final_columns = [
        "appointment_id",
        "appointment_date",
        "start_time",
        "appointment_type",
        "clinicId",
        "clinic",
        "no_show",
        "form_content",
        "form_link",
        "form_name",
        "month",
    ]
    # Keep only columns that exist (avoid errors if some are missing)
    existing_cols = [col for col in final_columns if col in merged.columns]
    final_df = merged[existing_cols]

    logger.info(f"Transformation complete. {len(final_df):,} rows, {len(final_df.columns)} columns.")
    logger.info(f"Forms found: {final_df['form_name'].notna().sum():,}")

    return final_df
