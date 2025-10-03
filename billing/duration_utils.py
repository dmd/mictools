#!/usr/bin/env python3

import datetime
import netrc
import requests
import pyorthanc
import time
import logging
import os


logger = logging.getLogger(__name__)


def setup_orthanc_connection(host, port=8042):
    """Setup Orthanc connection with netrc authentication."""
    server = f"http://{host}:{port}"

    try:
        netrc_file = os.path.expanduser("~/.netrc")
        username, _, password = netrc.netrc(netrc_file).authenticators(host)
    except (FileNotFoundError, TypeError):
        username, _, password = netrc.netrc("netrc").authenticators(host)

    o = pyorthanc.Orthanc(server, username=username, password=password)
    return o, server, username, password


def studies_for_date(study_date, client, query_filter=None):
    """Find studies for a given date with optional query filter."""
    query = {"StudyDate": study_date}
    if query_filter:
        query.update(query_filter)

    studies = pyorthanc.find_studies(client=client, query=query)
    return sorted(studies, key=lambda study: study.date)


def duration(study, server, username, password):
    """Calculate study duration from DICOM instance creation times."""
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
        min_time = min(instance_creation_datetimes)
        max_time = max(instance_creation_datetimes)
        return max_time - min_time, min_time
    except ValueError:
        return 0, None


def parse_date_range(arg):
    """Parse date argument and return list of dates to process."""
    dates = []

    if len(arg) == 6:  # YYYYMM format
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
            dates.append(f"{year:04d}{month:02d}{day:02d}")
    else:  # Assume YYYYMMDD format
        dates.append(arg)

    return dates


def format_duration_hms(study_duration):
    """Format duration as HH:MM:SS string."""
    if study_duration == 0:
        return "0"

    total_seconds = study_duration.total_seconds()
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
