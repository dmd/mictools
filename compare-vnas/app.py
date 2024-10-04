# app.py

from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# Constants
XNAT_BASE_URL = "https://iris.mclean.harvard.edu"
ORTHANC_URL = "http://micvna.mclean.harvard.edu:8042"

# Session objects
xs = requests.Session()
os = requests.Session()


def query_studies(study_date):
    url = f"{ORTHANC_URL}/tools/find"
    query_payload = {"Level": "Study", "Query": {"StudyDate": study_date}}
    response = os.post(url, json=query_payload)
    response.raise_for_status()  # Ensure we get a successful response
    return response.json()


def get_study_details(study_id):
    url = f"{ORTHANC_URL}/studies/{study_id}"
    response = os.get(url)
    response.raise_for_status()
    return response.json()


def get_recent_accession_numbers():
    accession_numbers = []
    for days_ago in range(3):
        study_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y%m%d")
        display_date = (datetime.now() - timedelta(days=days_ago)).strftime("%a %d")
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
                    accession_numbers.append((display_date, accession_number))

    return accession_numbers


def get_xnat_experiment_id(accession_number):
    response = xs.get(f"{XNAT_BASE_URL}/data/experiments?label={accession_number}")
    if response.status_code == 200:
        experiment_data = response.json()
        if experiment_data["ResultSet"]["Result"]:
            return experiment_data["ResultSet"]["Result"][0]["ID"]
    return None


def get_xnat_scans(experiment_id):
    response = xs.get(f"{XNAT_BASE_URL}/data/experiments/{experiment_id}/scans")
    if response.status_code == 200:
        return response.json()["ResultSet"]["Result"]
    return []


def get_xnat_frames(scan_uri):
    response = xs.get(f"{XNAT_BASE_URL}{scan_uri}?format=json")
    if response.status_code == 200:
        scan_info = response.json()
        children = scan_info["items"][0].get("children", [])
        for child in children:
            if "data_fields" in child["items"][0]:
                file_count = child["items"][0]["data_fields"].get("file_count")
                if file_count is not None:
                    return file_count
    return "N/A"


def get_orthanc_study_id(accession_number):
    query = {"Level": "Study", "Query": {"AccessionNumber": accession_number}}
    response = os.post(f"{ORTHANC_URL}/tools/find", json=query)
    if response.status_code == 200:
        study_ids = response.json()
        if study_ids:
            return study_ids[0]
    return None


def get_orthanc_series_ids(study_id):
    response = os.get(f"{ORTHANC_URL}/studies/{study_id}")
    if response.status_code == 200:
        return response.json().get("Series", [])
    return []


def get_orthanc_series_info(series_id):
    response = os.get(f"{ORTHANC_URL}/series/{series_id}")
    if response.status_code == 200:
        series_info = response.json()
        main_dicom_tags = series_info.get("MainDicomTags", {})
        series_number = main_dicom_tags.get("SeriesNumber", "N/A")
        series_description = main_dicom_tags.get("SeriesDescription", "N/A")
        instances = series_info.get("Instances", [])
        return str(series_number), series_description, len(instances)
    return None, None, 0


def compare_scans(xnat_scans, orthanc_scans):
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

    return sorted(combined_results.items(), key=lambda x: int(x[0].split("-")[0]))


def check_accession_number(accession_number):
    xnat_experiment_id = get_xnat_experiment_id(accession_number)
    xnat_scans = get_xnat_scans(xnat_experiment_id) if xnat_experiment_id else []

    orthanc_study_id = get_orthanc_study_id(accession_number)
    if orthanc_study_id:
        orthanc_series_ids = get_orthanc_series_ids(orthanc_study_id)
        orthanc_scans = [
            get_orthanc_series_info(series_id) for series_id in orthanc_series_ids
        ]
    else:
        orthanc_scans = []

    return compare_scans(xnat_scans, orthanc_scans)


@app.route("/")
def index():
    recent_accession_numbers = get_recent_accession_numbers()
    return render_template(
        "index.html", recent_accession_numbers=recent_accession_numbers
    )


@app.route("/check", methods=["POST"])
def check():
    accession_number = request.form["accession_number"]
    results = check_accession_number(accession_number)
    return jsonify({"results": results})


if __name__ == "__main__":
    app.run(debug=True)
