"""
sheets_logger.py
Handles all Google Sheets operations:
  - Find or create a spreadsheet by name
  - Find or create a tab (sheet) by day name
  - Add a header row if the sheet is empty
  - Append a new row: timestamp | speed | =IMAGE(url)
"""

import logging
from datetime import datetime
from typing import Optional

from googleapiclient.discovery import build
from core import auth

logger = logging.getLogger(__name__)

HEADER_ROW = ["Timestamp", "Speed Result", "Screenshot"]
DAYS_OF_WEEK = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday"
]

# Row height for screenshot rows (in pixels)
SCREENSHOT_ROW_HEIGHT = 300
SCREENSHOT_COL_WIDTH = 480  # Column C width


def _get_services(credentials_path: str):
    """Return authenticated Sheets and Drive service clients."""
    creds = auth.get_credentials(credentials_path)
    sheets = build("sheets", "v4", credentials=creds)
    drive = build("drive", "v3", credentials=creds)
    return sheets, drive


def _find_spreadsheet(drive_service, name: str) -> Optional[str]:
    """Search Drive for a spreadsheet by exact name. Returns spreadsheet ID or None."""
    query = (
        f"name='{name}' and "
        f"mimeType='application/vnd.google-apps.spreadsheet' and "
        f"trashed=false"
    )
    results = drive_service.files().list(
        q=query, spaces="drive", fields="files(id, name)"
    ).execute()
    files = results.get("files", [])
    if files:
        logger.debug(f"Found spreadsheet '{name}' (id={files[0]['id']})")
        return files[0]["id"]
    return None


def _create_spreadsheet(sheets_service, name: str) -> str:
    """Create a new spreadsheet with today's date tab. Returns spreadsheet ID."""
    today_str = datetime.now().strftime("%b %d %Y")
    body = {
        "properties": {"title": name},
        "sheets": [
            {"properties": {"title": today_str}}
        ]
    }
    spreadsheet = sheets_service.spreadsheets().create(
        body=body, fields="spreadsheetId"
    ).execute()
    spreadsheet_id = spreadsheet["spreadsheetId"]
    logger.info(f"Created spreadsheet '{name}' (id={spreadsheet_id})")
    return spreadsheet_id


def _get_or_create_spreadsheet(sheets_service, drive_service, name: str) -> str:
    """Return spreadsheet ID, creating the sheet if it doesn't exist."""
    existing_id = _find_spreadsheet(drive_service, name)
    if existing_id:
        return existing_id
    return _create_spreadsheet(sheets_service, name)


def _get_sheet_id(sheets_service, spreadsheet_id: str, tab_name: str) -> Optional[int]:
    """Get the numeric sheet ID for a named tab."""
    meta = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id
    ).execute()
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == tab_name:
            return props.get("sheetId")
    return None


def _ensure_tab_exists(sheets_service, spreadsheet_id: str, tab_name: str) -> int:
    """Ensure a named tab exists in the spreadsheet. Returns its numeric sheet ID."""
    sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, tab_name)
    if sheet_id is not None:
        return sheet_id

    # Add the tab
    body = {
        "requests": [{
            "addSheet": {
                "properties": {"title": tab_name}
            }
        }]
    }
    response = sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body=body
    ).execute()
    new_sheet_id = (
        response["replies"][0]["addSheet"]["properties"]["sheetId"]
    )
    logger.info(f"Created tab '{tab_name}' in spreadsheet {spreadsheet_id}")
    return new_sheet_id


def _get_row_count(sheets_service, spreadsheet_id: str, tab_name: str) -> int:
    """Return the number of rows currently in a tab."""
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab_name}'!A:A"
    ).execute()
    return len(result.get("values", []))


def _set_column_width(sheets_service, spreadsheet_id: str, sheet_id: int,
                      col_index: int, width: int):
    """Set the pixel width of a column."""
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": col_index,
                    "endIndex": col_index + 1
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize"
            }
        }]}
    ).execute()


def _set_row_height(sheets_service, spreadsheet_id: str, sheet_id: int,
                    row_index: int, height: int):
    """Set the pixel height of a specific row (0-indexed)."""
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": row_index,
                    "endIndex": row_index + 1
                },
                "properties": {"pixelSize": height},
                "fields": "pixelSize"
            }
        }]}
    ).execute()


def log_result(
    credentials_path: str,
    spreadsheet_name: str,
    speed_label: str,
    image_url: Optional[str] = None
) -> bool:
    """
    Append a new row to today's sheet tab in the given spreadsheet.

    Args:
        credentials_path: Path to the service account JSON credentials file.
        spreadsheet_name: Name of the Google Spreadsheet to log into.
        speed_label: Speed string (e.g. "95 Mbps") or "NO CONNECTION".
        image_url: Public Google Drive URL of the screenshot, or None.

    Returns:
        True on success, False on failure.
    """
    try:
        sheets_service, drive_service = _get_services(credentials_path)

        # Resolve spreadsheet
        spreadsheet_id = _get_or_create_spreadsheet(
            sheets_service, drive_service, spreadsheet_name
        )

        # Determine current day tab
        today = datetime.now().strftime("%b %d %Y")  # e.g. "Jun 18 2026"
        sheet_id = _ensure_tab_exists(sheets_service, spreadsheet_id, today)

        # Add header row if the sheet is empty
        row_count = _get_row_count(sheets_service, spreadsheet_id, today)
        if row_count == 0:
            sheets_service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"'{today}'!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [HEADER_ROW]}
            ).execute()
            row_count = 1
            # Apply global centering and format header row
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [
                    {
                        "repeatCell": {
                            "range": {"sheetId": sheet_id},
                            "cell": {
                                "userEnteredFormat": {
                                    "horizontalAlignment": "CENTER",
                                    "verticalAlignment": "MIDDLE",
                                    "wrapStrategy": "WRAP"
                                }
                            },
                            "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment,wrapStrategy)"
                        }
                    },
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 0,
                                "endRowIndex": 1
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "textFormat": {
                                        "bold": True,
                                        "foregroundColor": {
                                            "red": 0.0, "green": 0.0, "blue": 0.0
                                        }
                                    },
                                    "backgroundColor": {
                                        "red": 0.9, "green": 0.9, "blue": 0.9  # light gray
                                    }
                                }
                            },
                            "fields": "userEnteredFormat(textFormat(bold,foregroundColor),backgroundColor)"
                        }
                    }
                ]}
            ).execute()
            
        # Ensure column C is wide enough (doing this outside the if-block 
        # so it updates existing sheets that had the old smaller width)
        _set_column_width(sheets_service, spreadsheet_id, sheet_id, 2, SCREENSHOT_COL_WIDTH)

        # Build timestamp (Time only, since date is in the tab name)
        timestamp = datetime.now().strftime("%I:%M %p")

        # Build the row values
        if image_url:
            image_formula = f'=IMAGE("{image_url}")'
            row_values = [timestamp, speed_label, image_formula]
        else:
            row_values = [timestamp, speed_label, ""]

        # Append the row
        append_result = sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"'{today}'!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row_values]}
        ).execute()

        # Set row height for the new data row so screenshot is visible
        if image_url:
            new_row_index = row_count  # 0-indexed
            _set_row_height(
                sheets_service, spreadsheet_id, sheet_id,
                new_row_index, SCREENSHOT_ROW_HEIGHT
            )

        logger.info(
            f"Logged to '{spreadsheet_name}' → '{today}': "
            f"{timestamp} | {speed_label}"
        )
        return True

    except Exception as e:
        logger.error(f"Sheets logging failed: {e}")
        return False
