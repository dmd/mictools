#!/usr/bin/env python3

import sys
import csv
import datetime
import logging
import math
import os
from duration_utils import (
    setup_orthanc_connection,
    studies_for_date,
    duration,
    parse_date_range,
)


logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

host = "94tvna.mclean.harvard.edu"
port = 8042
FALLBACK_RATE = 9999

o, server, username, password = setup_orthanc_connection(host, port)

# Cache for billing lookup table
_billing_lookup = None
_row_counter = 2  # Start at row 2 (after header)


def load_billing_lookup():
    """Load the billing lookup table for 94T studies."""
    import os

    # Try /94tresearch/billing first, then current directory if not found
    possible_paths = [
        "/94tresearch/billing/billinglookup.tsv",  # primary location
        "billinglookup.tsv",  # current directory fallback
    ]

    lookup_dict = {}

    for lookup_file in possible_paths:
        if os.path.exists(lookup_file):
            try:
                with open(lookup_file, "r") as f:
                    reader = csv.DictReader(f, delimiter="\t")
                    for row in reader:
                        study_id = row["StudyID"]
                        fund_code = row["FundCode"]
                        pi_name = row["PIName"]
                        rate = row["Rate"]
                        lookup_dict[study_id] = {
                            "FundCode": fund_code,
                            "PIName": pi_name,
                            "Rate": int(rate) if rate.isdigit() else FALLBACK_RATE,
                        }
                logger.info(
                    f"Loaded {len(lookup_dict)} entries from billing lookup table at {lookup_file}"
                )
                return lookup_dict
            except Exception as e:
                logger.warning(
                    f"Failed to load billing lookup table from {lookup_file}: {e}"
                )
                continue

    # If no file found, log warning and return empty dict
    logger.warning(
        "No billing lookup table found in /94tresearch/billing or current directory"
    )
    return lookup_dict


def calculate_invoice_number(scan_date):
    """Calculate invoice number: 116 + months since May 2025"""
    may_2025 = datetime.date(2025, 5, 1)
    scan_date_obj = datetime.datetime.strptime(scan_date, "%Y%m%d").date()

    # Calculate months difference
    months_diff = (scan_date_obj.year - may_2025.year) * 12 + (
        scan_date_obj.month - may_2025.month
    )
    return 116 + months_diff


def get_study(study):
    global _row_counter
    service = "94T"

    # Handle StudyID lookup for 94T scanner
    study_id_tag = study.main_dicom_tags.get("StudyID", "missing")
    if study_id_tag != "missing":
        global _billing_lookup
        if _billing_lookup is None:
            _billing_lookup = load_billing_lookup()

        lookup_entry = _billing_lookup.get(study_id_tag)
        if lookup_entry:
            grant = lookup_entry["FundCode"]
            pi_name = lookup_entry["PIName"]
            rate = lookup_entry["Rate"]
        else:
            grant = study_id_tag
            pi_name = "UNKNOWN"
            rate = FALLBACK_RATE
    else:
        grant = study_id_tag
        pi_name = "UNKNOWN"
        rate = FALLBACK_RATE

    # Get duration and start time
    study_duration, start_time = duration(study, server, username, password)
    if study_duration == 0 or start_time is None:
        return  # Skip studies with 0 duration
    
    # Get current row number for Excel formula
    row_number = _row_counter

    # Calculate fields
    company = 1600
    total_hours = study_duration.total_seconds() / 3600
    quantity = math.ceil(total_hours * 4) / 4  # Round up to nearest 0.25
    total = rate * quantity

    # Calculate invoice number
    study_date = study.main_dicom_tags.get("StudyDate", "")
    invoice_number = calculate_invoice_number(study_date)

    # Format comment components
    start_time_formatted = start_time.strftime("%y%m%d%H%M")  # YYMMDDHHmm format

    # StudyID after underscore, truncated at 3 characters
    study_id_part = (
        study_id_tag.split("_")[-1][:3] if "_" in study_id_tag else study_id_tag[:3]
    )

    # First 4 characters of PI
    pi_part = pi_name[:4]

    comment = f"{grant}{start_time_formatted}{service}{study_id_part}_{pi_part}"

    # Run date format
    run_date = start_time.strftime("%Y-%m-%d")

    # Output row
    row = [
        company,
        grant,
        service,
        rate,
        quantity,
        pi_name,
        invoice_number,
f"=D{row_number}*E{row_number}",
        comment,
        run_date,
    ]

    writer = csv.writer(sys.stdout)
    writer.writerow(row)
    
    # Increment row counter for next study
    _row_counter += 1


def main():
    if len(sys.argv) != 2:
        print("Usage: duration94.py YYYYMM[DD]")
        sys.exit(1)
    arg = sys.argv[1]
    print("COMPANY,GRANT#,SERVICE,RATE,QUANTITY,PI,INVOICE#,TOTAL,COMMENT,RUNDATE")

    dates = parse_date_range(arg)
    for date in dates:
        for study in studies_for_date(date, o):
            get_study(study)


if __name__ == "__main__":
    main()
