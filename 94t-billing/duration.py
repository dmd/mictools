#!/usr/bin/env python3

import sys
import csv
import datetime
import netrc
import requests
import pyorthanc


host = "micvna.mclean.harvard.edu"
port = 8042
server = f"http://{host}:{port}"
username, _, password = netrc.netrc("netrc").authenticators(host)
o = pyorthanc.Orthanc(server, username=username, password=password)


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

def studies_for_date(study_date):
    query = {"StudyDate": study_date}
    studies = pyorthanc.find_studies(client=o, query=query)
    return studies

def main():
    if len(sys.argv) < 2:
        print("Usage: %s <accession number>" % sys.argv[0])
        sys.exit(1)


    accnum = sys.argv[1]
    query = {"AccessionNumber": accnum}
    studies = pyorthanc.find_studies(client=o, query=query)
    study = studies[0]

    if len(studies) == 0:
        print(f"No studies found with query {repr(query)}")
        sys.exit(1)

    data = {}
    data["date"] = study.date
    data["AccessionNumber"] = study.main_dicom_tags["AccessionNumber"]
    if study.main_dicom_tags["StudyDescription"].count("^") > 1:
        data["investigator"] = study.main_dicom_tags["StudyDescription"].split("^")[1]
    else:
        data["investigator"] = ""
    data["protocol"] = study.main_dicom_tags["StudyDescription"]
    data["duration"] = str(duration(study)).split(".")[0]

    writer = csv.writer(sys.stdout)
    writer.writerow(data.values())


if __name__ == "__main__":
    main()
