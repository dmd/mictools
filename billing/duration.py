#!/usr/bin/env python3

import sys
import csv
import datetime
import httpx
import logging
import pyorthanc
from duration_utils import (
    setup_orthanc_connection,
    studies_for_date,
    duration,
    parse_date_range,
    format_duration_hms,
)


logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

host = "micvna.mclean.harvard.edu"
port = 8042
o, server, username, password = setup_orthanc_connection(host, port)


def studies_for_date_filtered(study_date, qa_mode=False):
    if qa_mode:
        return studies_for_date(study_date, o)
    else:
        return studies_for_date(study_date, o, {"AccessionNumber": "E*"})


def get_study(study_id, qa_mode=False):
    if type(study_id) == str and study_id.startswith("E"):
        accnum = study_id
        query = {"AccessionNumber": accnum}
        studies = pyorthanc.find_studies(client=o, query=query)
        if len(studies) == 0:
            logger.error(f"No studies found with query {repr(query)}")
            sys.exit(1)
        study = studies[0]
    else:
        study = study_id

    data = {}
    
    # In QA mode, skip studies that start with "E"
    if qa_mode and study.main_dicom_tags["AccessionNumber"].startswith("E"):
        return
    
    data["date"] = study.date
    scanner_model = "?"
    # not every instance has the scanner model, so we need to loop through all instances
    for series in study.series:
        try:
            scanner_model = series.instances[0].get_content_by_tag("0008,1090")
            if scanner_model:
                break
        except httpx.HTTPError:
            continue

    data["scanner"] = {
        "MAGNETOM Prisma Fit": "P2",
        "MR MAGNETOM Prisma fit NX": "P2",
        "Prisma": "P1",
    }.get(scanner_model, scanner_model)
    data["AccessionNumber"] = study.main_dicom_tags["AccessionNumber"]
    data["patientid"] = study.patient_information["PatientID"]
    data["protocol"] = study.main_dicom_tags.get("StudyDescription", "missing")

    # Format duration as total hours:minutes:seconds
    study_duration, _ = duration(study, server, username, password)
    data["duration"] = format_duration_hms(study_duration)

    # sometimes reconstructs show up as 0
    if data["duration"] != "0":
        writer = csv.writer(sys.stdout)
        writer.writerow(data.values())


def main():
    qa_mode = False
    args = sys.argv[1:]
    
    # Check for --qa flag
    if "--qa" in args:
        qa_mode = True
        args.remove("--qa")
    
    if len(args) != 1:
        print("Usage: duration.py [--qa] YYYYMM[DD] | accession_number")
        print("  --qa: Include only QA scans (non-E accession numbers)")
        sys.exit(1)
    
    arg = args[0]
    print("datetime,scanner,accession_number,patientid,protocol,duration")
    
    if arg.startswith("E"):
        if qa_mode:
            print("Cannot use --qa flag with E accession numbers", file=sys.stderr)
            sys.exit(1)
        get_study(arg, qa_mode)
    else:
        dates = parse_date_range(arg)
        for date in dates:
            for study in studies_for_date_filtered(date, qa_mode):
                get_study(study, qa_mode)


if __name__ == "__main__":
    main()
