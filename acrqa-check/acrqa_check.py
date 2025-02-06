#!/usr/bin/env python3
import sys
import json
import datetime
import requests

def main():
    if len(sys.argv) != 2:
        print("Usage: python find_studies.py P1|P2")
        sys.exit(1)

    # The study description provided on the command line
    arg = sys.argv[1]
    if arg == "P1":
        study_description = "ACR WEEKLY^ACR WEEKLY^Weekly ACR P1"
    elif arg == "P2":
        study_description = "ACR WEEKLY ACR WEEKLY Weekly ACR P2"
    else:
        print("Error: Invalid argument. Use 'P1' or 'P2'.")
        sys.exit(1)

    # Calculate the date range for the last 30 days
    today = datetime.date.today()
    ten_days_ago = today - datetime.timedelta(days=30)
    start_date = ten_days_ago.strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")

    # Build the JSON query payload. The StudyDate field is a range in the form "YYYYMMDD-YYYYMMDD"
    payload = {
        "Level": "Study",
        "Query": {
            "StudyDate": f"{start_date}-{end_date}",
            "StudyDescription": study_description
        }
    }

    # URL for the find operation (adjust host and port if needed)
    orthanc_url = "http://micvna.mclean.harvard.edu:8042"
    find_endpoint = f"{orthanc_url}/tools/find"

    try:
        response = requests.post(find_endpoint, json=payload)
        response.raise_for_status()
    except requests.RequestException as e:
        print("Error querying Orthanc:", e)
        sys.exit(1)

    # The response is a JSON array of Orthanc IDs (one per study)
    study_ids = response.json()
    result = []
    if study_ids:
        # For each study ID, retrieve the study details (which include MainDicomTags)
        for study_id in study_ids:
            study_url = f"{orthanc_url}/studies/{study_id}"
            try:
                study_resp = requests.get(study_url)
                study_resp.raise_for_status()
            except requests.RequestException as e:
                print(f"Error retrieving study {study_id}:", e)
                continue

            study_info = study_resp.json()
            main_tags = study_info.get("MainDicomTags", {})
            study_date = main_tags.get("StudyDate", "Unknown")
            study_time = main_tags.get("StudyTime", "000000")

            # Format the datetime as YYYY-MM-DDTHH:mm:ss
            formatted_datetime = f"{study_date[:4]}-{study_date[4:6]}-{study_date[6:]}T{study_time[:2]}:{study_time[2:4]}:{study_time[4:6]}"
            result.append(formatted_datetime)

    if result:
        # Sort the results by datetime and get the most recent one
        result.sort(reverse=True)
        most_recent_study = result[0]

        # Calculate the number of seconds since the most recent study
        most_recent_datetime = datetime.datetime.strptime(most_recent_study, "%Y-%m-%dT%H:%M:%S")
        now = datetime.datetime.now()
        seconds_since_most_recent = int((now - most_recent_datetime).total_seconds())
        print(seconds_since_most_recent)
    else:
        print(9999999)

if __name__ == "__main__":
    main()