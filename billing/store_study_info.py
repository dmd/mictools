#!/usr/bin/env python3

"""Collect demographic and acquisition-specific information from an Orthanc
server and store the results in a local SQLite database.

Supported input tokens
----------------------
• Accession numbers starting with “E”.
• Date strings:  YYYYMM    – process every study for that month
                 YYYYMMDD  – process every study for that day

Only studies whose accession begins with “E” are recorded when running in
date mode.

Captured DICOM tags
-------------------
Per-study (recorded once):
    0010,1010  Patient Age (years, stored as integer)
    0010,1020  Patient Height (Size)
    0010,1030  Patient Weight
    0010,0040  Patient Sex
    0010,2160  Ethnic Group
    0018,0015  Body Part Examined
    0008,1090  Manufacturer Model Name
    0008,0020  Study Date

Per-series (recorded once *per series* when available):
    0018,1316  SAR (Specific Absorption Rate)
    0051,100a  Series Duration – stored in **seconds** (must decode strings like
               "TA 05:20")
    0020,0011  Series Number

A series is stored only if both SAR **and** duration are successfully
retrieved.

Database schema (auto-created on first run)
------------------------------------------
Table *studies*
    accession (PK) | patient_id | age | height | weight | sex | ethnic_group |
    body_part | manufacturer_model | study_date

Table *series*
    series_uid (PK) | accession (FK) | sar | duration | series_number

Usage examples
--------------
    ./store_study_info.py E12345678           # single accession
    ./store_study_info.py 20240427            # all studies on 27-Apr-2024
    ./store_study_info.py 202404              # all studies in April 2024

Progress reporting
------------------
When iterating over dates, each accession number that is processed is printed
to stdout before extraction begins so you can monitor progress.
"""

from __future__ import annotations

import argparse
import netrc
import os
import sqlite3
import sys
from typing import Any, Dict, Optional, Callable

import pydicom  # type: ignore
import pyorthanc
import datetime
import calendar


# ---------------------------------------------------------------------------
# Date helpers (for YYYYMM / YYYYMMDD selection)
# ---------------------------------------------------------------------------


def studies_for_date(date_str: str):
    """Return list of Study objects whose StudyDate equals *date_str* (YYYYMMDD)."""

    query = {"StudyDate": date_str}
    studies = pyorthanc.find_studies(client=ORTHANC, query=query)
    # Sort by date/time to keep deterministic order
    return sorted(studies, key=lambda s: (s.date, s.identifier))


# Callable already imported above via typing import Any, Dict, Optional, Callable


def process_date_arg(
    date_token: str,
    conn: sqlite3.Connection,
    *,
    force: bool = False,
    _skip_cb: Optional[Callable[[str], None]] = None,
) -> None:
    """Handle an argument that is a date (YYYYMM or YYYYMMDD).

    The *force* flag has the same semantics as in :func:`store_study` – when
    False, studies whose accession already exists in the database are skipped.
    When True, they are purged beforehand.
    """

    if len(date_token) == 8:  # YYYYMMDD
        # single day
        for study in studies_for_date(date_token):
            acc = study.main_dicom_tags.get("AccessionNumber", "")

            if not acc.startswith("E"):
                continue

            if accession_exists(conn, acc):
                if not force:
                    if _skip_cb:
                        _skip_cb(acc)
                    continue  # skip existing study
                # purge and reprocess before re-acquiring
                purge_accession(conn, acc)

            print(acc)
            _process_study(study, conn)

    elif len(date_token) == 6:  # YYYYMM -> full month
        year = int(date_token[:4])
        month = int(date_token[4:6])

        # Days in month
        days_in_month = calendar.monthrange(year, month)[1]

        for day in range(1, days_in_month + 1):
            date_str = f"{year:04d}{month:02d}{day:02d}"
            for study in studies_for_date(date_str):
                acc = study.main_dicom_tags.get("AccessionNumber", "")
                if not acc.startswith("E"):
                    continue

                if accession_exists(conn, acc):
                    if not force:
                        if _skip_cb:
                            _skip_cb(acc)
                        continue
                    purge_accession(conn, acc)

                print(acc)
                _process_study(study, conn)
    else:
        print(f"Invalid date token '{date_token}'. Expected YYYYMM or YYYYMMDD.", file=sys.stderr)


# ---------------------------------------------------------------------------
# Orthanc configuration (duplicated from duration.py for consistency)
# ---------------------------------------------------------------------------

HOST = "micvna.mclean.harvard.edu"
PORT = 8042
SERVER_URL = f"http://{HOST}:{PORT}"

# Credentials are stored in a *netrc* file next to this script (same scheme as
# duration.py)
try:
    USERNAME, _, PASSWORD = netrc.netrc("netrc").authenticators(HOST)
except FileNotFoundError:
    print("Could not locate 'netrc' file for Orthanc credentials.", file=sys.stderr)
    sys.exit(1)

ORTHANC = pyorthanc.Orthanc(SERVER_URL, username=USERNAME, password=PASSWORD)


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = "study_info.db"


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open (and create if missing) the SQLite database at *db_path* and ensure
    that the required tables exist.

    The function creates the file if it does not already exist and initialises
    the *studies* and *series* tables when they are missing.
    """

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS studies (
            accession          TEXT PRIMARY KEY,
            patient_id         TEXT,
            age                INTEGER,
            height             REAL,
            weight             REAL,
            sex                TEXT,
            ethnic_group       TEXT,
            body_part          TEXT,
            manufacturer_model TEXT,
            study_date         TEXT
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS series (
            series_uid     TEXT PRIMARY KEY,
            accession      TEXT NOT NULL,
            sar            REAL,
            duration       INTEGER,  -- seconds
            series_number  INTEGER,
            FOREIGN KEY (accession) REFERENCES studies(accession)
        )
        """
    )

    return conn


# ---------------------------------------------------------------------------
# DB convenience helpers
# ---------------------------------------------------------------------------


def accession_exists(conn: sqlite3.Connection, accession: str) -> bool:
    """Return *True* if *accession* is already present in *studies* table."""

    cur = conn.execute("SELECT 1 FROM studies WHERE accession = ? LIMIT 1", (accession,))
    return cur.fetchone() is not None


def purge_accession(conn: sqlite3.Connection, accession: str) -> None:
    """Remove *accession* from *studies* and all related rows from *series*."""

    # Delete child rows first to satisfy the foreign-key relation.
    conn.execute("DELETE FROM series WHERE accession = ?", (accession,))
    conn.execute("DELETE FROM studies WHERE accession = ?", (accession,))
    conn.commit()


# ---------------------------------------------------------------------------
# DICOM helpers
# ---------------------------------------------------------------------------

PATIENT_TAGS: Dict[str, str] = {
    "0010,1010": "age",
    "0010,1020": "height",
    "0010,1030": "weight",
    "0010,0040": "sex",
    "0010,2160": "ethnic_group",
}

BODY_PART_TAG = "0018,0015"  # Body Part Examined (study level)

MANUFACTURER_MODEL_TAG = "0008,1090"  # Manufacturer's Model Name
STUDY_DATE_TAG = "0008,0020"  # Study Date

SAR_TAG = "0018,1316"  # Specific Absorption Rate

SERIES_DURATION_TAG = "0051,100a"  # Series duration (per series)

SERIES_NUMBER_TAG = "0020,0011"  # Series Number


def extract_patient_tags(ds: pydicom.FileDataset) -> Dict[str, Optional[str]]:
    """Return the subset of *ds* that corresponds to *PATIENT_TAGS*.

    The values are normalised to strings when present, otherwise *None* is
    returned for missing tags.
    """

    result: Dict[str, Optional[str]] = {}
    for tag, name in PATIENT_TAGS.items():
        elem = ds.get(tag)
        if elem is None:
            # pydicom accepts tags as (group, element) tuples as well; convert:
            group, element = (int(tag[0:4], 16), int(tag[5:], 16))
            elem = ds.get((group, element))

        if elem is None or elem.value in ("", None):  # type: ignore[attr-defined]
            parsed_value: Optional[Any] = None
        else:
            raw_str = str(elem.value).strip()  # type: ignore[attr-defined]

            if tag == "0010,1010":  # Age
                # Expect strings like "040Y" or "30Y"; keep digits before any letter
                digits = "".join(ch for ch in raw_str if ch.isdigit())
                parsed_value = int(digits) if digits else None
            else:
                parsed_value = raw_str

        result[name] = parsed_value

    return result


def get_element(ds: pydicom.FileDataset, tag_str: str):
    """Helper to retrieve element from dataset *ds* given a string "GGGG,EEEE" tag."""

    elem = ds.get(tag_str)
    if elem is None:
        group, element = (int(tag_str[0:4], 16), int(tag_str[5:], 16))
        elem = ds.get((group, element))
    return elem


def extract_body_part(ds: pydicom.FileDataset) -> Optional[str]:
    """Return Body Part Examined (0018,0015) as string or None."""

    elem = get_element(ds, BODY_PART_TAG)
    if elem is None or elem.value in ("", None):  # type: ignore[attr-defined]
        return None
    return str(elem.value)  # type: ignore[attr-defined]


def extract_series_duration(ds: pydicom.FileDataset) -> Optional[float]:
    """Return series duration (0051,100a) in *seconds* as an int.

    The vendor–specific private tag usually looks like the string

        "TA mm:ss"

    where *mm* is minutes and *ss* is seconds.  Occasionally the value can be a
    bare number representing seconds (Siemens XA versions write just a float).
    The function attempts to cope with both representations and falls back to
    *None* when parsing fails.
    """

    elem = get_element(ds, SERIES_DURATION_TAG)
    if elem is None or elem.value in ("", None):  # type: ignore[attr-defined]
        return None

    raw_value = str(elem.value).strip()  # type: ignore[attr-defined]

    # Case 1: numeric – assume already in seconds.
    try:
        return int(float(raw_value))
    except ValueError:
        pass

    # Case 2: prefixed with "TA "
    if raw_value.upper().startswith("TA "):
        raw_value = raw_value[3:].strip()

    # Expect now a time string mm:ss or hh:mm:ss
    parts = raw_value.split(":")
    try:
        parts_int = [int(p) for p in parts]
    except ValueError:
        return None

    if len(parts_int) == 2:  # mm:ss
        minutes, seconds = parts_int
        total = minutes * 60 + seconds
        return total
    elif len(parts_int) == 3:  # hh:mm:ss
        hours, minutes, seconds = parts_int
        total = hours * 3600 + minutes * 60 + seconds
        return total

    return None


def extract_sar(ds: pydicom.FileDataset) -> Optional[float]:
    """Return the SAR (0018,1316) value as a *float* if present, otherwise *None*."""

    elem = ds.get(SAR_TAG)
    if elem is None:
        # Try numeric tuple notation
        elem = ds.get((0x0018, 0x1316))

    if elem is None or elem.value in ("", None):  # type: ignore[attr-defined]
        return None

    # The VR for SAR is FD (floating point double).  We try to coerce to float.
    try:
        return float(elem.value)  # type: ignore[arg-type,attr-defined]
    except (TypeError, ValueError):
        # Some manufacturers store the value as a string such as "1.23" or "1.23  mW/kg".
        try:
            return float(str(elem.value).split()[0])  # type: ignore[attr-defined]
        except ValueError:
            return None


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


# Internal routine that does the actual database operations ------------------


def _process_study(study: pyorthanc.Study, conn: sqlite3.Connection) -> None:
    """Store desired information from *study* into *conn*."""

    # Use the very first DICOM instance of the study to populate patient tags.
    # This prevents multiple requests for identical information and avoids the
    # need to tap directly into Orthanc's database.
    # Core identifiers
    accession = study.main_dicom_tags.get("AccessionNumber")

    first_instance = study.series[0].instances[0]
    ds_first = first_instance.get_pydicom()

    patient_info = extract_patient_tags(ds_first)
    body_part = extract_body_part(ds_first)

    # Manufacturer model: try first instance; if missing, search others
    elem_mm = get_element(ds_first, MANUFACTURER_MODEL_TAG)
    manufacturer_model = (
        None
        if elem_mm is None or elem_mm.value in ("", None)  # type: ignore[attr-defined]
        else str(elem_mm.value)  # type: ignore[attr-defined]
    )

    if manufacturer_model is None:
        # scan other instances until found
        for series in study.series:
            for inst in series.instances:
                try:
                    val = inst.get_content_by_tag(MANUFACTURER_MODEL_TAG)
                    if val:
                        manufacturer_model = val
                        break
                except Exception:
                    continue
            if manufacturer_model is not None:
                break

    study_date = study.main_dicom_tags.get("StudyDate")
    patient_id = study.patient_information.get("PatientID")

    # Insert or update the *studies* table.
    conn.execute(
        """
        INSERT INTO studies (
            accession, patient_id, age, height, weight, sex, ethnic_group, body_part,
            manufacturer_model, study_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(accession) DO UPDATE SET
            patient_id          = excluded.patient_id,
            age                 = COALESCE(excluded.age, studies.age),
            height              = COALESCE(excluded.height, studies.height),
            weight              = COALESCE(excluded.weight, studies.weight),
            sex                 = COALESCE(excluded.sex, studies.sex),
            ethnic_group        = COALESCE(excluded.ethnic_group, studies.ethnic_group),
            body_part           = COALESCE(excluded.body_part, studies.body_part),
            manufacturer_model  = COALESCE(excluded.manufacturer_model, studies.manufacturer_model),
            study_date          = COALESCE(excluded.study_date, studies.study_date)
        """,
        (
            accession,
            patient_id,
            patient_info["age"],
            patient_info["height"],
            patient_info["weight"],
            patient_info["sex"],
            patient_info["ethnic_group"],
            body_part,
            manufacturer_model,
            study_date,
        ),
    )

    # Iterate over every series in the study and store SAR.
    for series in study.series:
        series_uid = series.uid

        # Check if we already stored this series.
        cur = conn.execute("SELECT 1 FROM series WHERE series_uid = ?", (series_uid,))
        if cur.fetchone() is not None:
            continue

        # Retrieve SAR and duration from the first instance.
        try:
            ds = series.instances[0].get_pydicom()
            sar = extract_sar(ds)
            duration = extract_series_duration(ds)

            # Requirements: both SAR and duration present
            if sar is None or duration is None:
                continue

            # SeriesNumber (0020,0011)
            elem_sn = get_element(ds, SERIES_NUMBER_TAG)
            if elem_sn is not None and elem_sn.value not in ("", None):  # type: ignore[attr-defined]
                try:
                    series_number = int(str(elem_sn.value).split()[0])  # type: ignore[attr-defined]
                except ValueError:
                    series_number = None
            else:
                series_number = None

            conn.execute(
                """
                INSERT INTO series (series_uid, accession, sar, duration, series_number)
                VALUES (?, ?, ?, ?, ?)
                """,
                (series_uid, accession, sar, duration, series_number),
            )

        except Exception as exc:
            print(f"Failed to fetch series {series_uid}: {exc}", file=sys.stderr)

    conn.commit()


# Public helper --------------------------------------------------------------


def store_study(accession: str, conn: sqlite3.Connection, *, force: bool = False) -> None:
    """Locate study by *accession* and store its information.

    Behaviour is influenced by *force*:

    • If *force* is False (default) and the accession already exists in the
      database, the function returns immediately.
    • If *force* is True, any existing rows for the accession (including
      related *series*) are removed before the data are retrieved again from
      Orthanc.
    """

    if accession_exists(conn, accession):
        if not force:
            # Skip silently – caller decides whether to print something.
            return

        # Remove stale data before re-importing.
        purge_accession(conn, accession)

    studies = pyorthanc.find_studies(client=ORTHANC, query={"AccessionNumber": accession})

    if not studies:
        print(f"No study found for accession number {accession}", file=sys.stderr)
        return

    _process_study(studies[0], conn)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Store DICOM demographics and SAR information in SQLite.")
    parser.add_argument(
        "tokens",
        nargs="+",
        help="Accession numbers starting with 'E', or date strings YYYYMM / YYYYMMDD",
    )

    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help=(
            "Re-fetch information even if the accession already exists in the local "
            "database. When used, existing rows for that accession (including related "
            "series) are removed before acquisition."
        ),
    )

    parser.add_argument(
        "--db",
        metavar="PATH",
        default="study_info.db",
        help="Path to the SQLite database file to use (default: study_info.db)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    conn = get_db_connection(args.db)

    def _print_skip(acc: str) -> None:
        print(f"{acc} already in db, skipping")

    for token in args.tokens:
        if token.startswith("E"):
            if not args.force and accession_exists(conn, token):
                _print_skip(token)
                continue

            store_study(token, conn, force=args.force)
        elif token.isdigit() and len(token) in (6, 8):
            process_date_arg(token, conn, force=args.force, _skip_cb=_print_skip)
        else:
            print(
                f"Unrecognised argument '{token}'. Expected accession starting with 'E' or date string.",
                file=sys.stderr,
            )

    conn.close()


if __name__ == "__main__":
    main()
