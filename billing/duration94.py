#!/usr/bin/env python3

import sys
import csv
import datetime
import netrc
import requests
import pyorthanc
import httpx
import time
import logging
import math
import os


logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

host = "94tvna.mclean.harvard.edu"
port = 8042
server = f"http://{host}:{port}"

try:
    netrc_file = os.path.expanduser("~/.netrc")
    username, _, password = netrc.netrc(netrc_file).authenticators(host)
except (FileNotFoundError, TypeError):
    username, _, password = netrc.netrc("netrc").authenticators(host)
o = pyorthanc.Orthanc(server, username=username, password=password)

# Cache for billing lookup table
_billing_lookup = None


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
                        lookup_dict[study_id] = {
                            "FundCode": fund_code,
                            "PIName": pi_name,
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


def studies_for_date(study_date):
    query = {"StudyDate": study_date}
    studies = pyorthanc.find_studies(client=o, query=query)
    return sorted(studies, key=lambda study: study.date)


def duration(study):
    # Use bulk-content as it's vastly faster than the pyorthanc method; retry on transient connection errors.
    while True:
        try:
            data = requests.post(
                server + "/tools/bulk-content",
                json={"Resources": [study.identifier], "Level": "Instance"},
                auth=(username, password),
            ).json()
            logger.info(f"Getting {study.identifier}")
            break
        except Exception as e:
            logger.warning(f"Warning: {e}, retrying in 1 second...")
            time.sleep(1)

    instance_creation_datetimes = []

    for item in data:
        if (
            "MainDicomTags" in item
            and "InstanceCreationDate" in item["MainDicomTags"]
            and "InstanceCreationTime" in item["MainDicomTags"]
        ):
            datetime_str = (
                item["MainDicomTags"]["InstanceCreationDate"]
                + item["MainDicomTags"]["InstanceCreationTime"]
            )

            # Try both formats - with and without microseconds
            for fmt in ["%Y%m%d%H%M%S.%f", "%Y%m%d%H%M%S"]:
                try:
                    dt = datetime.datetime.strptime(datetime_str, fmt)
                    instance_creation_datetimes.append(dt)
                    break
                except ValueError:
                    continue

    try:
        return max(instance_creation_datetimes) - min(instance_creation_datetimes), min(
            instance_creation_datetimes
        )
    except ValueError:
        return 0, None


def calculate_invoice_number(scan_date):
    """Calculate invoice number: 116 + months since May 2025"""
    may_2025 = datetime.date(2025, 5, 1)
    scan_date_obj = datetime.datetime.strptime(scan_date, "%Y%m%d").date()

    # Calculate months difference
    months_diff = (scan_date_obj.year - may_2025.year) * 12 + (
        scan_date_obj.month - may_2025.month
    )
    return 116 + months_diff


def get_study(study_id):
    if type(study_id) == str and study_id.startswith("9T"):
        accnum = study_id
        query = {"AccessionNumber": accnum}
        studies = pyorthanc.find_studies(client=o, query=query)
        if len(studies) == 0:
            logger.error(f"No studies found with query {repr(query)}")
            sys.exit(1)
        study = studies[0]
    else:
        study = study_id

    scanner_model = "?"
    # not every instance has the scanner model, so we need to loop through all instances
    for series in study.series:
        try:
            scanner_model = series.instances[0].get_content_by_tag("0008,1090")
            if scanner_model:
                break
        except httpx.HTTPError:
            continue

    service = {
        "MAGNETOM Prisma Fit": "P2",
        "MR MAGNETOM Prisma fit NX": "P2",
        "Prisma": "P1",
        "BAP94/30": "94",
        "Datastation": "94",
    }.get(scanner_model, scanner_model)

    # Handle StudyID lookup for 94T scanner
    study_id_tag = study.main_dicom_tags.get("StudyID", "missing")
    if service == "94" and study_id_tag != "missing":
        global _billing_lookup
        if _billing_lookup is None:
            _billing_lookup = load_billing_lookup()

        lookup_entry = _billing_lookup.get(study_id_tag)
        if lookup_entry:
            grant = lookup_entry["FundCode"]
            pi_name = lookup_entry["PIName"]
        else:
            grant = study_id_tag
            pi_name = "UNKNOWN"
    else:
        grant = study_id_tag
        pi_name = "UNKNOWN"

    # Get duration and start time
    study_duration, start_time = duration(study)
    if study_duration == 0 or start_time is None:
        return  # Skip studies with 0 duration

    # Calculate fields
    company = 1600
    rate = 600
    total_hours = study_duration.total_seconds() / 3600
    quantity = math.ceil(total_hours * 4) / 4  # Round up to nearest 0.25
    total = rate * quantity

    # Calculate invoice number
    study_date = study.main_dicom_tags.get("StudyDate", "")
    invoice_number = calculate_invoice_number(study_date)

    # Format comment components
    start_time_formatted = start_time.strftime("%y%m%d%H%M")  # YYMMDDHHmm format

    # StudyID after underscore, truncated at 6 characters
    study_id_part = (
        study_id_tag.split("_")[-1][:6] if "_" in study_id_tag else study_id_tag[:6]
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
        int(total),
        comment,
        run_date,
    ]

    writer = csv.writer(sys.stdout)
    writer.writerow(row)


def main():
    if len(sys.argv) != 2:
        print("Usage: duration94.py YYYYMM[DD] | accession_number")
        sys.exit(1)
    arg = sys.argv[1]
    # Print header
    print("COMPANY,GRANT#,SERVICE,RATE,QUANTITY,PI,INVOICE#,TOTAL,COMMENT,RUNDATE")
    if arg.startswith("9T"):
        get_study(arg)
    elif len(arg) == 6:
        year, month = int(arg[:4]), int(arg[4:6])
        # Handle December properly by rolling over to the next year
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1

        for day in range(
            1,
            (
                datetime.date(next_year, next_month, 1) - datetime.date(year, month, 1)
            ).days
            + 1,
        ):
            for study in studies_for_date(f"{year:04d}{month:02d}{day:02d}"):
                get_study(study)
    else:
        for study in studies_for_date(arg):
            get_study(study)


if __name__ == "__main__":
    main()
