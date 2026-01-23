#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
import os
import xml.etree.ElementTree as ET
from datetime import datetime

DOCBOOK_NS = "http://docbook.org/ns/docbook"
NS = {"db": DOCBOOK_NS}


def parse_number(text):
    if text is None:
        return None
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if not match:
        return None
    return float(match.group(0))


def truncate_number(value, decimals=4):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    factor = 10**decimals
    truncated = int(value * factor) / factor
    if truncated.is_integer():
        return int(truncated)
    return truncated


def find_table_by_title(root, title):
    for table in root.findall(".//db:table", NS):
        t = table.find("db:title", NS)
        if t is not None and (t.text or "").strip() == title:
            return table
    return None


def get_table_label_value(table, label):
    for row in table.findall(".//db:row", NS):
        entries = [(e.text or "").strip() for e in row.findall("db:entry", NS)]
        if len(entries) >= 2 and entries[0] == label:
            return entries[1]
    return None


def get_column_values(table, header_name):
    header_entries = [
        (e.text or "").strip() for e in table.findall(".//db:thead//db:entry", NS)
    ]
    col_idx = None
    for i, h in enumerate(header_entries):
        if h == header_name or h.startswith(header_name):
            col_idx = i
            break
    if col_idx is None:
        return []

    values = []
    for row in table.findall(".//db:tbody/db:row", NS):
        entries = [(e.text or "").strip() for e in row.findall("db:entry", NS)]
        if len(entries) > col_idx:
            values.append(entries[col_idx])
    return values


def iter_scan_dirs(study_path: Path) -> list[Path]:
    scan_dirs: list[tuple[int, Path]] = []
    with os.scandir(study_path) as entries:
        for entry in entries:
            if not entry.is_dir():
                continue
            if not entry.name.isdigit():
                continue
            scan_dirs.append((int(entry.name), Path(entry.path)))
    scan_dirs.sort(key=lambda item: item[0])
    return [p for _, p in scan_dirs]


def iter_recon_dirs(scan_dir: Path) -> list[Path]:
    pdata_dir = scan_dir / "pdata"
    if not pdata_dir.is_dir():
        return []
    recon_dirs: list[tuple[int | str, Path]] = []
    with os.scandir(pdata_dir) as entries:
        for entry in entries:
            if not entry.is_dir():
                continue
            key: int | str = int(entry.name) if entry.name.isdigit() else entry.name
            recon_dirs.append((key, Path(entry.path)))
    recon_dirs.sort(key=lambda item: item[0])
    return [p for _, p in recon_dirs]


def find_report_paths(study_path: Path) -> tuple[list[Path], Path | None]:
    # Bruker QA reports are typically located under:
    #   <scan>/pdata/<recon>/reports/QASnrReport/QASnrReport.xml
    #   <scan>/pdata/<recon>/reports/QAGhostReport/QAGhostReport.xml
    qasnr_paths: list[Path] = []
    first_ghost_path: Path | None = None
    for scan_dir in iter_scan_dirs(study_path):
        for recon_dir in iter_recon_dirs(scan_dir):
            qasnr_path = (
                recon_dir / "reports" / "QASnrReport" / "QASnrReport.xml"
            )
            if qasnr_path.is_file():
                qasnr_paths.append(qasnr_path)
            if first_ghost_path is None:
                ghost_path = (
                    recon_dir / "reports" / "QAGhostReport" / "QAGhostReport.xml"
                )
                if ghost_path.is_file():
                    first_ghost_path = ghost_path
    return qasnr_paths, first_ghost_path


def extract_qasnr_metrics(qasnr_paths):
    frequency = None
    max_snr = None
    min_inhomogeneity = None
    min_inhomogeneity_fraction = None
    for path in qasnr_paths:
        root = ET.parse(path).getroot()

        if frequency is None:
            table = find_table_by_title(root, "System Information")
            if table is not None:
                value = get_table_label_value(table, "Frequency")
                if value:
                    frequency = parse_number(value)

        table = find_table_by_title(root, "Image specific SNR values")
        if table is not None:
            values = get_column_values(table, "Normalized SNR")
            for v in values:
                num = parse_number(v)
                if num is None:
                    continue
                if max_snr is None or num > max_snr:
                    max_snr = num

        table = find_table_by_title(root, "Slice specific Homogeneity values")
        if table is not None:
            values = get_column_values(table, "Homogeneity")
            for v in values:
                num = parse_number(v)
                if num is None:
                    continue
                if min_inhomogeneity is None or num < min_inhomogeneity:
                    min_inhomogeneity = num
                    min_inhomogeneity_fraction = num / 100.0 if "%" in v else num

    if max_snr is not None and max_snr.is_integer():
        max_snr = int(max_snr)

    return frequency, max_snr, min_inhomogeneity_fraction


def extract_maxghost(first_ghost_path):
    root = ET.parse(first_ghost_path).getroot()
    table = find_table_by_title(root, "Ghost Quantification")
    if table is None:
        return None
    values = get_column_values(table, "Max. Ghost ROI / Max. Signal")
    max_value = None
    max_fraction = None
    for v in values:
        num = parse_number(v)
        if num is None:
            continue
        if max_value is None or num > max_value:
            max_value = num
            max_fraction = num / 100.0 if "%" in v else num
    return max_fraction


def study_datetime_from_name(study_name: str) -> tuple[datetime, str]:
    match = re.match(r"(\d{8})_(\d{6})", study_name)
    if not match:
        raise ValueError("Study name does not start with YYYYMMDD_HHmmSS.")

    study_date, study_time = match.groups()
    study_dt = datetime.strptime(
        f"{study_date}{study_time}",
        "%Y%m%d%H%M%S",
    )

    try:
        from zoneinfo import ZoneInfo

        study_dt = study_dt.replace(tzinfo=ZoneInfo("America/New_York"))
        datetime_value = study_dt.isoformat(timespec="milliseconds")
    except Exception:
        datetime_value = study_dt.strftime("%Y-%m-%dT%H:%M:%S.000")

    return study_dt, datetime_value


def extract_study_metrics(study_path: Path) -> tuple[datetime, dict]:
    if not study_path.exists():
        raise SystemExit(f"Study path does not exist: {study_path}")

    study_name = study_path.name
    try:
        study_dt, datetime_value = study_datetime_from_name(study_name)
    except ValueError as e:
        raise SystemExit(str(e))

    qasnr_paths, first_ghost = find_report_paths(study_path)
    if not qasnr_paths:
        raise SystemExit("No QASnrReport.xml files found.")
    if first_ghost is None:
        raise SystemExit("No QAGhostReport.xml files found.")

    frequency, normalized_snr, inhomogeneity = extract_qasnr_metrics(qasnr_paths)
    maxghost = extract_maxghost(first_ghost)

    if frequency is None:
        raise SystemExit("Frequency not found.")
    if normalized_snr is None:
        raise SystemExit("Normalized SNR not found.")
    if inhomogeneity is None:
        raise SystemExit("Inhomogeneity not found.")
    if maxghost is None:
        raise SystemExit("Max ghost value not found.")

    output = {
        "study": study_name,
        "datetime": datetime_value,
        "frequency": truncate_number(frequency),
        "normalized_snr": truncate_number(normalized_snr),
        "inhomogeneity": truncate_number(inhomogeneity),
        "maxghost": truncate_number(maxghost),
    }

    return study_dt, output


def main():
    parser = argparse.ArgumentParser(
        description="Extract QA metrics from one or more study directories."
    )
    parser.add_argument(
        "study_paths",
        nargs="+",
        help="One or more study directories",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output JSON path (defaults to <study>-qa.json for one input, qa.json for multiple)",
    )
    args = parser.parse_args()

    outputs_with_dt = []
    for study_path_str in args.study_paths:
        study_path = Path(study_path_str)
        try:
            outputs_with_dt.append(extract_study_metrics(study_path))
        except SystemExit as e:
            raise SystemExit(f"{study_path}: {e}")

    outputs_with_dt.sort(key=lambda x: x[0])
    outputs = [o for _, o in outputs_with_dt]

    if args.output:
        output_path = Path(args.output)
    elif len(outputs) == 1:
        output_path = Path.cwd() / f"{outputs[0]['study']}-qa.json"
    else:
        output_path = Path.cwd() / "qa.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(outputs, f, indent=2)
        f.write("\n")

    print(output_path)


if __name__ == "__main__":
    main()
