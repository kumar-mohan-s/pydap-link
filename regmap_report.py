"""Create portable, timestamped scan evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from regmap_executor import summarize
from regmap_model import ScanResult, format_hex


def default_output_path(input_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return input_path.with_name(f"{input_path.stem}_results_{timestamp}{input_path.suffix}")


def build_metadata(input_path: Path, profile_name: str) -> dict[str, str]:
    return {
        "Run Timestamp UTC": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "Input Path": str(input_path.resolve()),
        "Profile": profile_name,
    }


def save_results(
    results: list[ScanResult], output_path: Path, metadata: dict[str, str]
) -> None:
    rows = [_result_row(result, metadata) for result in results]
    frame = pd.DataFrame(rows)
    if output_path.suffix.lower() == ".csv":
        frame.to_csv(output_path, index=False)
    elif output_path.suffix.lower() == ".xlsx":
        with pd.ExcelWriter(output_path) as writer:
            frame.to_excel(writer, sheet_name="Results", index=False)
            pd.DataFrame(metadata.items(), columns=["Field", "Value"]).to_excel(
                writer, sheet_name="Run Metadata", index=False
            )
    else:
        raise ValueError("Results path must end in .csv or .xlsx.")


def summary_text(results: list[ScanResult]) -> str:
    summary = summarize(results)
    return (
        f"{summary['total']} total | {summary['passed']} verified | "
        f"{summary['transport_only']} transport-only | {summary['failed']} failed"
    )


def _result_row(result: ScanResult, metadata: dict[str, str]) -> dict[str, str]:
    check = result.check
    row = {
        "S.No": check.sequence,
        "Register Name": check.name,
        "Access": check.access.value,
        "Address": format_hex(check.address),
        "Width": str(check.width_bits),
        "Requested Value": format_hex(check.value, check.width_bits),
        "Expected": format_hex(check.expected, check.width_bits),
        "Mask": format_hex(check.mask, check.width_bits),
        "Observed Value": format_hex(result.observed_value, check.width_bits),
        "Original Value": format_hex(result.original_value, check.width_bits),
        "Restored Value": format_hex(result.restored_value, check.width_bits),
        "Verification": check.verification.value,
        "Status": result.status.value,
    }
    return {**metadata, **row}
