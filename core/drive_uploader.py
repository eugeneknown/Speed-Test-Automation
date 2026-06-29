"""
drive_uploader.py
Handles uploading screenshots to Google Drive using a Service Account.
Creates an ISP-specific folder under the configured root folder.
Makes files publicly readable so =IMAGE() in Sheets works without auth.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from core import auth

logger = logging.getLogger(__name__)


def _get_drive_service(credentials_path: str):
    """Build and return an authenticated Google Drive service client."""
    creds = auth.get_credentials(credentials_path)
    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service, name: str, parent_id: Optional[str] = None) -> str:
    """
    Find an existing Drive folder by name (and optional parent), or create it.
    Returns the folder ID.
    """
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)"
    ).execute()

    files = results.get("files", [])
    if files:
        logger.debug(f"Found existing folder '{name}' (id={files[0]['id']})")
        return files[0]["id"]

    # Create the folder
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder"
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    logger.info(f"Created Drive folder '{name}' (id={folder['id']})")
    return folder["id"]


def _make_public(service, file_id: str):
    """Grant public read access to a Drive file so =IMAGE() works in Sheets."""
    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"}
    ).execute()


def upload_screenshot(
    credentials_path: str,
    screenshot_path: Path,
    isp_name: str,
    root_folder_name: str = "SpeedTest Results"
) -> Tuple[bool, str]:
    """
    Upload a screenshot to Google Drive under:
        <root_folder_name>/<isp_name>/

    Returns:
        (success: bool, image_url: str)
        image_url is the direct embed URL usable in =IMAGE() formula.
    """
    try:
        service = _get_drive_service(credentials_path)

        # Ensure folder structure exists
        root_id = _get_or_create_folder(service, root_folder_name)
        isp_folder_id = _get_or_create_folder(service, isp_name, parent_id=root_id)

        # Upload the file
        file_metadata = {
            "name": screenshot_path.name,
            "parents": [isp_folder_id]
        }
        media = MediaFileUpload(str(screenshot_path), mimetype="image/png")
        uploaded = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()

        file_id = uploaded["id"]
        logger.info(f"Uploaded screenshot to Drive (id={file_id})")

        # Make publicly accessible for =IMAGE()
        _make_public(service, file_id)

        # Build the direct image URL
        image_url = f"https://drive.google.com/uc?export=view&id={file_id}"
        return True, image_url

    except Exception as e:
        logger.error(f"Drive upload failed: {e}")
        return False, ""
