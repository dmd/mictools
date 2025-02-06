#!/usr/bin/env python3

import sys
import csv
import datetime
import netrc
import requests
import pyorthanc
import httpx


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
    # use bulk-content as it's vastly faster than the pyorthanc method

    datetime_format = "%Y%m%d%H%M%S.%f"

    data = requests.post(
        server + "/tools/bulk-content",
        json={"Resources": [study.identifier], "Level": "Instance"},
        auth=(username, password),
    ).json()

    instance_creation_datetimes = [
        datetime.datetime.strptime(
            item["MainDicomTags"]["InstanceCreationDate"]
            + item["MainDicomTags"]["InstanceCreationTime"],
            datetime_format,
        )
        for item in data
        if "MainDicomTags" in item
        and "InstanceCreationDate" in item["MainDicomTags"]
        and "InstanceCreationTime" in item["MainDicomTags"]
    ]

    return max(instance_creation_datetimes) - min(instance_creation_datetimes)


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
    try:
        scanner_model = study.series[0].instances[0].get_content_by_tag("0008,1090")
    except httpx.HTTPError:
        scanner_model = "?"

    data["scanner"] = {"MAGNETOM Prisma Fit": "P2", "MR MAGNETOM Prisma fit NX": "P2", "Prisma": "P1"}.get(
        scanner_model, scanner_model
    )
    data["AccessionNumber"] = study.main_dicom_tags["AccessionNumber"]
    data["patientid"] = study.patient_information["PatientID"]
    data["protocol"] = study.main_dicom_tags["StudyDescription"]
    data["duration"] = str(duration(study)).split(".")[0]

    writer = csv.writer(sys.stdout)
    writer.writerow(data.values())


def main():
    if len(sys.argv) != 2:
        print("Usage: duration.py YYYYMM[DD] | accession_number")
        sys.exit(1)
    arg = sys.argv[1]
    if arg.startswith("E"):
        get_study(arg)
    elif len(arg) == 6:
        year, month = int(arg[:4]), int(arg[4:6])
        for day in range(
            1,
            (datetime.date(year, month + 1, 1) - datetime.date(year, month, 1)).days
            + 1,
        ):
            for study in studies_for_date(f"{year:04d}{month:02d}{day:02d}"):
                get_study(study)
    else:
        for study in studies_for_date(arg):
            get_study(study)


if __name__ == "__main__":
    main()
