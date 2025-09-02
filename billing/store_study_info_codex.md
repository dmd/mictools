# store_study_info – Codex Notes

Internal working notes for continuing development / maintenance of
`store_study_info.py`.  

---

## Current Objective

Collect specific DICOM metadata for MRI studies stored in an Orthanc server and
persist the results in a local SQLite database.  The tool is now feature-
complete for the first iteration but these notes capture *why* things look the
way they do and what caveats to remember when extending it.

## Running the script

```console
# Single accession
./store_study_info.py E12345678

# All studies on a given day
./store_study_info.py 20240427

# All studies in a month
./store_study_info.py 202404

# Multiple tokens are accepted
./store_study_info.py 202404 20240427 E87654321

# Force re-acquisition even if the accession is already stored
./store_study_info.py --force E12345678
```

### Token rules

| Pattern        | Meaning                          |
|----------------|----------------------------------|
| `E…`           | A single accession number.        |
| 8 digits       | `YYYYMMDD` – specific day.        |
| 6 digits       | `YYYYMM`   – entire month.        |

When in *date mode* (6/8-digit tokens) the script prints each accession number
to stdout as it is processed **but only if it begins with `E`** (studies with
other accession formats are ignored).

## Orthanc connection

```
HOST = "micvna.mclean.harvard.edu"
PORT = 8042
```

Credentials are retrieved from the local `netrc` file (same as `duration.py`).

Dependencies: `pyorthanc`, `pydicom`, and Python 3.10+ stdlib.

## Database – `study_info.db`

Created automatically if absent; **schema is rebuilt by simply deleting the
file**.  Two tables:

### studies

| column              | type    | note                                                |
|---------------------|---------|-----------------------------------------------------|
| accession           | TEXT PK | must start with `E`                                 |
| patient_id          | TEXT    |                                                    |
| age                 | INTEGER | years – derived from `0010,1010`                    |
| height              | REAL    | `0010,1020`, may be decimal string                  |
| weight              | REAL    | `0010,1030`                                         |
| sex                 | TEXT    | `0010,0040`                                         |
| ethnic_group        | TEXT    | `0010,2160`                                         |
| body_part           | TEXT    | `0018,0015`                                         |
| manufacturer_model  | TEXT    | `0008,1090`                                         |
| study_date          | TEXT    | `0008,0020` (YYYYMMDD)                              |
| study_description   | TEXT    | `0008,1030`                                         |

### series

| column        | type    | note                                                       |
|---------------|---------|------------------------------------------------------------|
| series_uid    | TEXT PK | Orthanc UID                                                |
| accession     | TEXT FK | links back to *studies*                                    |
| sar           | REAL    | `0018,1316` – must be present or row is skipped            |
| duration      | INTEGER | seconds; parsed from `0051,100a` (“TA mm:ss”) **required** |
| series_number       | INTEGER | `0020,0011`; NULL if missing/non-numeric                  |
| series_description  | TEXT    | `0008,103e`                                                |
| pulse_sequence_name | TEXT    | `0018,9005`                                                |
| sequence_name       | TEXT    | `0018,0024`                                                |

## Tag handling summary

| Tag        | Stored as          | Level   | Notes                                               |
|------------|-------------------|---------|-----------------------------------------------------|
| 0010,1010  | age INTEGER       | study   | strip trailing letter, keep digits (years)          |
| 0010,1020  | height REAL       | study   |                                                     |
| 0010,1030  | weight REAL       | study   |                                                     |
| 0010,0040  | sex TEXT          | study   |                                                     |
| 0010,2160  | ethnic_group TEXT | study   |                                                     |
| 0018,0015  | body_part TEXT    | study   |                                                     |
| 0008,1090  | manufacturer_model| study   | tries first instance, otherwise scans others        |
| 0008,0020  | study_date TEXT       | study   | from Study MainDicomTags                            |
| 0008,1030  | study_description TEXT| study   |                                                     |
| 0018,1316  | sar REAL              | series  | required                                            |
| 0051,100a  | duration INTEGER      | series  | required; seconds; Siemens private tag             |
| 0020,0011  | series_number INT     | series  | may be NULL                                         |
| 0008,103e  | series_description TEXT| series  |                                                     |
| 0018,9005  | pulse_sequence_name TEXT| series  |                                                     |
| 0018,0024  | sequence_name TEXT      | series  |                                                     |

## Business rules & edge cases

1. **Series skipping** – if SAR *or* duration unavailable ⇒ series not stored.
2. **Age extraction** – expects strings like `040Y`, `30Y`; keeps leading
   digits, converts to int; NULL if parse fails.
3. **Duration parsing** – handles:
   * Vendor private string "TA mm:ss" or "TA hh:mm:ss".
   * Pure numeric seconds (float or int).
4. **Date mode filtering** – ignore studies whose accession doesn't start with
   `E`.
5. **Duration tag (0051,100a)** – Siemens-specific private tag; may be missing in:
   * Non-Siemens scanners
   * Localizer/scout sequences
   * Some sequence types or older software versions

## Code structure cheatsheet

* `_process_study(study, conn)` – main logic for a single Study object.
* `store_study(acc, conn)`     – lookup by accession then delegates to above.
* `process_date_arg(token, conn)` – expands YYYYMM / YYYYMMDD to studies.
* Helper functions: `extract_*`, `get_element`, etc.

## Potential improvements / TODOs

* Parallelise series downloads (currently serial). Orthanc API can cope.
* Add CLI switch to output CSV in addition to DB.
* Error-handling: maybe explicit logging instead of stderr prints.
* Configurability for Orthanc host/port via env vars or CLI.
* Unit tests using a mocked Orthanc server.

---

**End of Codex notes**
