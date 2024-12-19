#!/usr/bin/env python3

import requests
import sys
from datetime import datetime
import subprocess
from operator import itemgetter


# URLs for XNAT and Orthanc
xnat_base_url = "https://iris.mclean.harvard.edu"
orthanc_url = "http://micvna.mclean.harvard.edu:8042"

xs = requests.Session()
os = requests.Session()


# Function to get the current date in YYYYMMDD format
def get_date():
    if len(sys.argv) > 1 and len(sys.argv[1]) == 8 and sys.argv[1].isdigit():
        return sys.argv[1]  # Take the first command-line argument as the date
    else:
        return datetime.today().strftime("%Y%m%d")  # Default to today's date


# Function to query the API for studies
def query_studies(study_date):
    url = f"{orthanc_url}/tools/find"
    query_payload = {"Level": "Study", "Query": {"StudyDate": study_date}}
    response = os.post(url, json=query_payload)
    response.raise_for_status()  # Ensure we get a successful response
    return response.json()


# Function to query individual study details
def get_study_details(study_id):
    url = f"{orthanc_url}/studies/{study_id}"
    response = os.get(url)
    response.raise_for_status()
    return response.json()


# Function to fetch the experiment ID using the accession number (XNAT)
def get_xnat_experiment_id(accession_number):
    response = xs.get(f"{xnat_base_url}/data/experiments?label={accession_number}")
    if response.status_code == 200:
        experiment_data = response.json()
        if experiment_data["ResultSet"]["Result"]:
            return experiment_data["ResultSet"]["Result"][0]["ID"]
    return None


# Function to fetch scans for the given experiment ID (XNAT)
def get_xnat_scans(experiment_id):
    response = xs.get(f"{xnat_base_url}/data/experiments/{experiment_id}/scans")
    if response.status_code == 200:
        return response.json()["ResultSet"]["Result"]
    return []


# Function to fetch the number of frames for a given scan using its URI (XNAT)
def get_xnat_frames(scan_uri):
    response = xs.get(f"{xnat_base_url}{scan_uri}?format=json")
    if response.status_code == 200:
        scan_info = response.json()
        children = scan_info["items"][0].get("children", [])
        for child in children:
            if "data_fields" in child["items"][0]:
                file_count = child["items"][0]["data_fields"].get("file_count")
                if file_count is not None:
                    return file_count
    return "N/A"


# Function to get study ID based on accession number (Orthanc)
def get_orthanc_study_id(accession_number):
    query = {"Level": "Study", "Query": {"AccessionNumber": accession_number}}
    response = os.post(f"{orthanc_url}/tools/find", json=query)
    if response.status_code == 200:
        study_ids = response.json()
        if study_ids:
            return study_ids[0]  # Assuming the first study ID is the one we want
    return None


# Function to get series IDs from the study (Orthanc)
def get_orthanc_series_ids(study_id):
    response = os.get(f"{orthanc_url}/studies/{study_id}")
    if response.status_code == 200:
        return response.json().get("Series", [])
    return []


# Function to get series info for a given series ID (Orthanc)
def get_orthanc_series_info(series_id):
    response = os.get(f"{orthanc_url}/series/{series_id}")
    if response.status_code == 200:
        series_info = response.json()
        main_dicom_tags = series_info.get("MainDicomTags", {})
        series_number = main_dicom_tags.get("SeriesNumber", "N/A")
        series_description = main_dicom_tags.get("SeriesDescription", "N/A")
        instances = series_info.get("Instances", [])
        return int(series_number), series_description, len(instances)
    return None, None, 0


# Function to compare scans and highlight mismatches
def compare_scans(xnat_scans, orthanc_scans, print_details=True):
    combined_results = {}

    for scan in xnat_scans:
        scan_id = scan["ID"]
        frames = get_xnat_frames(scan["URI"])
        combined_results[scan_id] = {
            "xnat_description": scan["series_description"],
            "xnat_frames": frames,
            "orthanc_description": "MISSING",
            "orthanc_frames": "MISSING",
        }

    for series_number, series_description, num_instances in orthanc_scans:
        scan_id = str(series_number)
        if scan_id in combined_results:
            combined_results[scan_id]["orthanc_description"] = series_description
            combined_results[scan_id]["orthanc_frames"] = num_instances
        else:
            combined_results[scan_id] = {
                "xnat_description": "MISSING",
                "xnat_frames": "MISSING",
                "orthanc_description": series_description,
                "orthanc_frames": num_instances,
            }

    sorted_results = sorted(
        combined_results.items(), key=lambda x: int(x[0].split("-")[0])
    )

    any_mismatch = False
    ignore_mismatch = False
    if print_details:
        print(
            f"{'Δ':<1} {'ID':>5} {'MICVNA #':>12} {'Desc':<30} {'XNAT #':>18} {'Desc':<30}"
        )
    for scan_id, scan_info in sorted_results:
        mismatch = ""
        if (scan_info["xnat_frames"] != scan_info["orthanc_frames"]) or (
            scan_info["xnat_description"] != scan_info["orthanc_description"]
        ):
            mismatch = "*"
            if int(scan_id.split("-")[0]) < 98:
                any_mismatch = True
            else:
                ignore_mismatch = True
                mismatch = "w"
        if print_details:
            print(
                f"{mismatch:<1} {scan_id:>5} {scan_info['orthanc_frames']:>12} {scan_info['orthanc_description']:<30} {scan_info['xnat_frames']:>18} {scan_info['xnat_description']:<30}"
            )
    if ignore_mismatch:
        print("ignoring series>98 mismatch")

    if len(sorted_results) == 0:
        return True

    return any_mismatch


# Function to check a single accession number
def check_accession_number(accession_number, print_details=True):
    # XNAT side
    xnat_experiment_id = get_xnat_experiment_id(accession_number)
    if xnat_experiment_id:
        xnat_scans = get_xnat_scans(xnat_experiment_id)
    else:
        xnat_scans = []

    # Orthanc side
    orthanc_study_id = get_orthanc_study_id(accession_number)
    if orthanc_study_id:
        orthanc_series_ids = get_orthanc_series_ids(orthanc_study_id)
        orthanc_scans = [
            get_orthanc_series_info(series_id) for series_id in orthanc_series_ids
        ]
    else:
        orthanc_scans = []

    # Compare and print results
    any_mismatch = compare_scans(xnat_scans, orthanc_scans, print_details)
    return "PROBLEM" if any_mismatch else "OK"


# Function to check studies for a given date
def check_studies_for_date(study_date):
    all_ok = True
    print(f"Querying studies for date: {study_date}")
    study_ids = query_studies(study_date)

    for study_id in study_ids:
        study_details = get_study_details(study_id)
        study_description = study_details.get("MainDicomTags", {}).get(
            "StudyDescription", ""
        )

        if study_description.startswith("Investigators"):
            accession_number = study_details.get("MainDicomTags", {}).get(
                "AccessionNumber", ""
            )

            if accession_number:
                status = check_accession_number(accession_number, print_details=False)
                print(f"{accession_number}  {status}")
                if status != "OK":
                    all_ok = False

    return all_ok


def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith("E"):
        # If an accession number is provided, check that specific study
        accession_number = sys.argv[1]
        status = check_accession_number(accession_number, print_details=True)
        print(f"{accession_number}  {status}")
        sys.exit(1 if status == "PROBLEM" else 0)
    else:
        # Otherwise, check studies for the given date or today's date
        study_date = get_date()
        if not check_studies_for_date(study_date):
            sys.exit(1)


if __name__ == "__main__":
    main()
