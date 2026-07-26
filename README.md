# Register Map Scanner

`regmap_scan.py` is a Python command-line tool for validating approved ARM Cortex-M register maps through a pyOCD-compatible CMSIS-DAP probe. It loads a CSV or XLSX manifest, validates every row before contacting hardware, performs the approved reads or writes, and writes a CSV or XLSX result report.

The included `samv71q21` profile and `register_map_template.csv` provide a read-only starting point for an ATSAMV71Q21 target. The scanner does not reset, erase or program flash.

## Workflow

The PlantUML workflow is in [`regmap_scan_workflow.puml`](regmap_scan_workflow.puml).

Render it with a PlantUML extension or a local PlantUML installation when a diagram image is needed.

## Requirements

- Python 3.10 or later
- A pyOCD-compatible CMSIS-DAP debug probe
- A pyOCD target definition or CMSIS Device Family Pack for the selected MCU

Install the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Probe And Target Discovery

List connected probes:

```powershell
pyocd list
```

List the installed SAM V71 targets:

```powershell
pyocd list --targets --name atsamv71q21
```

For the validated SAM V71 setup, pyOCD reports:

```text
Target: atsamv71q21
Probe:  Atmel Corp. EDBG CMSIS-DAP
```

Use the target name reported by the installed pyOCD environment. Do not assume that a similar device name is interchangeable.

## Operating The Scanner

Run a dry validation first. This parses the manifest and validates it against the selected profile without opening a probe.

```powershell
python regmap_scan.py --input register_map_template.csv --dry-run
```

Run the read-only SAM V71 scan. Replace the probe UID with the value returned by `pyocd list` when necessary.

```powershell
python regmap_scan.py --input register_map_template.csv --output samv71_readonly_results.csv --target atsamv71q21 --probe ATML2407060200000078
```

Use `--verbose` to include pyOCD connection and discovery logs:

```powershell
python regmap_scan.py --input register_map_template.csv --target atsamv71q21 --probe ATML2407060200000078 --verbose
```

The default profile is `samv71q21`. The available profiles can be shown with:

```powershell
python regmap_scan.py --help
```

## Manifest Format

The scanner requires these columns:

| Column | Purpose |
|---|---|
| `S.No` | Unique row identifier. |
| `Register Name` | Profile-approved register name. |
| `Access` | `R`, `W`, or `RW`. |
| `Address` | 32-bit register or memory address in decimal or `0x...` format. |
| `Value` | Required value for `W` and `RW` rows. |

These optional columns control the operation:

| Column | Purpose |
|---|---|
| `Width` | Access width: `8`, `16`, or `32`; defaults to `32`. |
| `Expected` | Expected value for exact or masked verification. |
| `Mask` | Bit mask for masked verification. |
| `Verification` | `record`, `exact`, `masked`, or `transport`. |
| `Safety` | `read_only` or `scratch`. |
| `Requires Halt` | Whether the scanner must halt the core before the check; defaults to `true`. |
| `Restore` | Restores the original value after an `RW` scratch-memory check. |

The included SAM V71 template contains only approved read-only checks. For a profile-selected manifest, the register name, address, width, access mode, verification rule, expected value, and mask must match the approved profile entry.

## Result Reports

Each hardware run writes a CSV or XLSX report. The CSV includes the selected target and probe metadata plus the requested, expected, observed, original, and restored values where applicable.

The following statuses are possible:

| Status | Meaning |
|---|---|
| `PASS` | The read or read-back verification passed. |
| `PASS_TRANSPORT_ONLY` | A write completed, but the register is write-only and cannot be read back. |
| `FAIL` | A transport operation or verification comparison failed. |

If Windows reports that the selected output file is in use, close the application holding the file or choose a different `--output` path.

## Safety Model

- The current target profiles permit read-only checks only.
- The scanner requires `--enable-writes` and an explicit `--scratch-range <start>:<size>` before it will consider a write operation.
- A write entry must be marked `Safety=scratch` and must fall fully within the supplied scratch range.
- `RW` scratch tests read the original value, write and verify the requested value, then restore the original value.
- The session attaches without pyOCD's default reset or automatic resume behavior. The scanner only resumes a core that it halted itself.

Do not designate general-purpose RAM as scratch memory without confirming that it is reserved by the firmware linker map and safe for debugger access.

## Tests

Run the automated tests:

```powershell
python -m unittest discover -s tests -v
```

Compile the source files:

```powershell
python -m compileall -q .
```

## Planned Work

The following are intentionally not part of the current implementation..

- verify write-capable profile entries after reviewing codebase.
- Add reviewed, device-specific profiles for additional Cortex-M microcontrollers.
- Add XLSX reporting
