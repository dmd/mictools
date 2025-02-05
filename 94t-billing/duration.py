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


def get_date():
    if len(sys.argv) > 1 and len(sys.argv[1]) == 8 and sys.argv[1].isdigit():
        return sys.argv[1]
    else:
        return datetime.datetime.today().strftime("%Y%m%d")


def studies_for_date(study_date):
    query = {"StudyDate": study_date}
    studies = pyorthanc.find_studies(client=o, query=query)
    return studies


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
    data["AccessionNumber"] = study.main_dicom_tags["AccessionNumber"]
    sd = study.main_dicom_tags["StudyDescription"]
    if sd.startswith("Investigators^") or sd.startswith("McLean Research^"):
        data["investigator"] = sd.split("^")[1]
    else:
        data["investigator"] = "clinical"
    data["protocol"] = sd
    data["duration"] = str(duration(study)).split(".")[0]

    writer = csv.writer(sys.stdout)
    writer.writerow(data.values())


def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith("E"):
        get_study(sys.argv[1])
    else:
        for study in studies_for_date(get_date()):
            get_study(study)


if __name__ == "__main__":
    main()
