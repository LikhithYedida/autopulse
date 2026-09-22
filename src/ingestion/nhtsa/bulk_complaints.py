from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests


# ============================================================
# AutoPulse AI
# NHTSA Bulk Complaint Ingestion
# ============================================================

SOURCE_URL = (
    "https://static.nhtsa.gov/odi/ffdd/cmpl/"
    "COMPLAINTS_RECEIVED_2025-2026.zip"
)

RAW_DATA_DIR = Path(
    "data/raw/nhtsa/complaints"
)

FILE_NAME = "COMPLAINTS_RECEIVED_2025-2026.zip"

OUTPUT_PATH = RAW_DATA_DIR / FILE_NAME

METADATA_PATH = RAW_DATA_DIR / (
    "COMPLAINTS_RECEIVED_2025-2026.metadata.json"
)


def download_file(
    url: str,
    output_path: Path,
) -> dict:
    """
    Download a file using streaming so large NHTSA
    datasets do not need to be loaded entirely into memory.

    A SHA-256 checksum is calculated during ingestion.
    """

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = output_path.with_suffix(
        output_path.suffix + ".part"
    )

    sha256 = hashlib.sha256()

    total_bytes = 0

    print("=" * 70)
    print("AUTOPULSE — NHTSA BULK INGESTION")
    print("=" * 70)

    print(f"Source: {url}")
    print(f"Destination: {output_path}")
    print("\nDownloading...")

    with requests.get(
        url,
        stream=True,
        timeout=120,
    ) as response:

        response.raise_for_status()

        expected_size = int(
            response.headers.get(
                "content-length",
                0,
            )
        )

        with open(temp_path, "wb") as file:

            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):

                if not chunk:
                    continue

                file.write(chunk)

                sha256.update(chunk)

                total_bytes += len(chunk)

                downloaded_mb = (
                    total_bytes / 1024 / 1024
                )

                print(
                    f"\rDownloaded: "
                    f"{downloaded_mb:,.2f} MB",
                    end="",
                )

        metadata = {
            "source_system": "NHTSA",
            "dataset": "consumer_complaints",
            "source_url": url,
            "file_name": output_path.name,
            "retrieved_at_utc": (
                datetime.now(timezone.utc)
                .isoformat()
            ),
            "bytes_downloaded": total_bytes,
            "expected_bytes": expected_size,
            "sha256": sha256.hexdigest(),
            "content_type": response.headers.get(
                "content-type"
            ),
            "last_modified": response.headers.get(
                "last-modified"
            ),
            "etag": response.headers.get(
                "etag"
            ),
        }

    temp_path.replace(output_path)

    return metadata


def save_metadata(
    metadata: dict,
    metadata_path: Path,
) -> None:
    """
    Save ingestion metadata for traceability
    and reproducibility.
    """

    with open(
        metadata_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metadata,
            file,
            indent=2,
        )


def main():
    metadata = download_file(
        url=SOURCE_URL,
        output_path=OUTPUT_PATH,
    )

    save_metadata(
        metadata=metadata,
        metadata_path=METADATA_PATH,
    )

    print("\n\nDownload complete.")

    print(
        f"File size: "
        f"{metadata['bytes_downloaded'] / 1024 / 1024:,.2f} MB"
    )

    print(
        f"SHA-256: "
        f"{metadata['sha256']}"
    )

    print(
        f"Source last modified: "
        f"{metadata['last_modified']}"
    )

    print(
        f"Metadata saved to: "
        f"{METADATA_PATH}"
    )


if __name__ == "__main__":
    main()