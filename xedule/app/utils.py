# app/utils.py

import pandas as pd

from .models import Note

TWEET_LENGTH = 280


def process_excel_file(excel_file, user):
    """Process the uploaded Excel file and create tweets."""
    result = {
        "success": False,
        "tweets_created": 0,
        "tweets_failed": 0,
        "error_messages": [],
        "message": "",
    }

    try:
        # Read Excel file
        data_table = pd.read_excel(excel_file, engine="openpyxl")

        # Check required columns
        if "content" not in data_table.columns:
            result["message"] = "The Excel file must contain a 'content' column."
            return result

        # Process rows
        row_results = [
            process_row(index, row, data_table, user)
            for index, row in data_table.iterrows()
        ]
        result["notes_created"] = sum(1 for r in row_results if r["success"])
        result["notes_failed"] = sum(1 for r in row_results if not r["success"])
        result["error_messages"] = [
            r["message"] for r in row_results if not r["success"]
        ]
        result["success"] = True

    except (FileNotFoundError, ValueError, pd.errors.ExcelFileError) as e:
        result["message"] = f"Error processing the Excel file: {e!s}"

    return result


def process_row(index, row, data_table, user):
    """Process a single row from the Excel file."""
    try:
        content = validate_content(index, row)
        scheduled_time = handle_scheduled_time(index, row, data_table)
        publish_to_x = handle_publish_to_x(row, data_table)
        publish_to_nostr = handle_publish_to_nostr(row, data_table)

        Note.objects.create(
            user=user,
            content=content,
            scheduled_time=scheduled_time,
            publish_to_x=publish_to_x,
            publish_to_nostr=publish_to_nostr,
            status="pending",
        )

    except ValueError as e:
        return {"success": False, "message": f"Row {index + 1}: {e!s}"}

    else:
        return {"success": True}


class ContentValidationError(ValueError):
    """Custom exception for content validation errors."""

    def __init__(self, message):
        super().__init__(message)


def validate_content(index, row):
    """Validate the content of a note."""
    if pd.isna(row.get("content")) or row.get("content") == "":
        msg = "Content is required."
        raise ContentValidationError(msg)
    content = str(row["content"])
    if len(content) > TWEET_LENGTH:
        msg = "Content exceeds 280 characters."
        raise ContentValidationError(msg)
    return content


def handle_scheduled_time(index, row, data_table):
    """Handle the scheduled time for a note."""
    if "scheduled_time" in data_table.columns and not pd.isna(
        row.get("scheduled_time")
    ):
        return row["scheduled_time"]
    return None


def handle_publish_to_x(row, data_table):
    """Handle the publish_to_x flag."""
    if "publish_to_x" in data_table.columns and not pd.isna(row.get("publish_to_x")):
        value = row["publish_to_x"]
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ["yes", "true", "1", "y", "si", "sí"]
        if isinstance(value, (int, float)):
            return bool(value)
    return False


def handle_publish_to_nostr(row, data_table):
    """Handle the publish_to_nostr flag."""
    if "publish_to_nostr" in data_table.columns and not pd.isna(
        row.get("publish_to_nostr")
    ):
        value = row["publish_to_nostr"]
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ["yes", "true", "1", "y", "si", "sí"]
        if isinstance(value, (int, float)):
            return bool(value)
    return False
