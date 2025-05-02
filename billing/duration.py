#!/usr/bin/env python3

import sys
import csv
import datetime
import netrc
import requests
import pyorthanc
import httpx
import time


host = "micvna.mclean.harvard.edu"
port = 8042
server = f"http://{host}:{port}"
username, _, password = netrc.netrc("netrc").authenticators(host)
o = pyorthanc.Orthanc(server, username=username, password=password)


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
            print(f"Getting {study.identifier}", file=sys.stderr)
            break
        except:
            print(f"Error, retrying in 1 second...", file=sys.stderr)
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
        return max(instance_creation_datetimes) - min(instance_creation_datetimes)
    except ValueError:
        return 0


def get_study(study_id):
    if type(study_id) == str and study_id.startswith("E"):
        accnum = study_id
        query = {"AccessionNumber": accnum}
        studies = pyorthanc.find_studies(client=o, query=query)
        if len(studies) == 0:
            print(f"No studies found with query {repr(query)}")
            sys.exit(1)
        study = studies[0]
    else:
        study = study_id

    data = {}
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
        "BAP94/30": "94T",
    }.get(scanner_model, scanner_model)
    data["AccessionNumber"] = study.main_dicom_tags["AccessionNumber"]
    data["patientid"] = study.patient_information["PatientID"]
    data["protocol"] = study.main_dicom_tags.get("StudyDescription", "missing")

    # Format duration as total hours:minutes:seconds
    study_duration = duration(study)
    if study_duration == 0:
        data["duration"] = "0"
    else:
        total_seconds = study_duration.total_seconds()
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        data["duration"] = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

    # sometimes reconstructs show up as 0
    if data["duration"] != "0":
        writer = csv.writer(sys.stdout)
        writer.writerow(data.values())


def main():
    if len(sys.argv) != 2:
        print("Usage: duration.py YYYYMM[DD] | accession_number")
        sys.exit(1)
    arg = sys.argv[1]
    print("datetime,scanner,accession_number,patientid,protocol,duration")
    if arg.startswith("E"):
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
