#!/usr/bin/env python3
"""Safe, profile-driven Cortex-M register-map scanner using pyOCD."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from regmap_executor import execute_scan, summarize
from regmap_manifest import (
    ManifestValidationError,
    load_manifest,
    parse_scratch_range,
    validate_runtime_policy,
)
from regmap_profiles import get_profile, profile_names
from regmap_pyocd import PyOcdConnection
from regmap_report import build_metadata, default_output_path, save_results, summary_text


LOG = logging.getLogger("regmap_scan")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Profile-driven Cortex-M register-map validation scanner."
    )
    parser.add_argument("--input", required=True, type=Path, help="CSV or XLSX register manifest")
    parser.add_argument("--output", type=Path, help="CSV or XLSX results path")
    parser.add_argument(
        "--profile", choices=profile_names(), default="samv71q21", help="Approved target profile"
    )
    parser.add_argument("--target", help="Exact pyOCD target name required for hardware scans")
    parser.add_argument("--probe", help="CMSIS-DAP probe UID; optional when exactly one probe is present")
    parser.add_argument("--pack", type=Path, help="Optional CMSIS Device Family Pack path")
    parser.add_argument("--dry-run", action="store_true", help="Validate manifest and profile only")
    parser.add_argument("--no-halt", action="store_true", help="Reject checks that require a halted core")
    parser.add_argument("--enable-writes", action="store_true", help="Permit approved scratch-memory writes")
    parser.add_argument(
        "--scratch-range", help="Approved write range as <start>:<size>, for example 0x2045F000:0x100"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    _configure_logging(args.verbose)

    try:
        checks = load_manifest(args.input)
        profile = get_profile(args.profile)
        profile.validate(checks)
        scratch_range = parse_scratch_range(args.scratch_range) if args.scratch_range else None
    except (FileNotFoundError, ManifestValidationError) as exc:
        LOG.error("Manifest validation failed:\n%s", exc)
        return 1

    LOG.info("Validated %d check(s) against profile '%s'.", len(checks), profile.name)
    if args.dry_run:
        LOG.info("Dry run complete. No debug probe was opened.")
        return 0
    if not args.target:
        LOG.error("--target is required for a hardware scan; do not rely on target auto-detection.")
        return 1
    if args.no_halt and any(check.requires_halt for check in checks):
        LOG.error("--no-halt conflicts with one or more checks marked Requires Halt=true.")
        return 1

    try:
        validate_runtime_policy(checks, args.enable_writes, scratch_range)
    except ManifestValidationError as exc:
        LOG.error("Runtime policy rejected the scan:\n%s", exc)
        return 1

    output_path = args.output or default_output_path(args.input)
    metadata = build_metadata(args.input, profile.name)
    connection = PyOcdConnection(args.target, args.probe, args.pack)
    results = []
    try:
        with connection as target:
            LOG.info(
                "Connected: probe=%s uid=%s target=%s",
                target.probe_description,
                target.selected_probe_uid,
                target.target_part_number,
            )
            target.halt_if_needed(not args.no_halt and any(check.requires_halt for check in checks))
            results = execute_scan(checks, target)
    except Exception as exc:  # Session failures have no per-register result to serialize.
        LOG.error("Hardware scan aborted: %s: %s", type(exc).__name__, exc)
        return 1

    metadata.update(connection.metadata())
    try:
        save_results(results, output_path, metadata)
    except OSError as exc:
        LOG.error("Could not write results to %s: %s", output_path, exc)
        return 1
    summary = summarize(results)
    LOG.info("Results written to %s", output_path)
    LOG.info("Summary: %s", summary_text(results))
    if summary["failed"]:
        return 2
    return 0


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


if __name__ == "__main__":
    sys.exit(main())
