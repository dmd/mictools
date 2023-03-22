#!/usr/bin/env python3

from pathlib import Path
import arrow
from glob import glob
from shutil import copyfile
import subprocess
import argparse
import json
import logging
import re

logging.basicConfig(
    level=logging.DEBUG,
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    format="{asctime} {levelname} {filename}:{lineno}: {message}",
)

root_in = "/qc/mriqc/in/p1"
root_out = "/qc/mriqc/out/p1"

niigz = ".nii.gz"


def final_scan(sourcenames):
    #  given ['FOO_BAR_11.nii.gz', 'FOO_BAR_2.nii.gz', 'FOO_BAR_3.nii.gz']
    #  return 'FOO_BAR_11.nii.gz', the highest numbered scan

    if not sourcenames:
        return []

    files = {}
    for file in sourcenames:

        m = re.search(rf"_(\d+){niigz}$", file)
        fid = int(m.group(1))

        if fid not in files:
            files[fid] = []
        files[fid].append(file)

    ids = sorted(list(files.keys()))
    return files[max(ids)][0]

def copy_to_in_folder(bids, nifti_name, ident, bids_name):
    Path(f"{bids}/sub-{ident}/func").mkdir(parents=True, exist_ok=True)
    open(f"{bids}/dataset_description.json", "w").write(
        """{"Name": "none","BIDSVersion": "1.2.0","Authors": ["x"]}"""
    )
    bids_filename = f"{bids}/sub-{ident}/func/sub-{ident}_{bids_name}_bold.nii.gz"
    try:
        copyfile(nifti_name, bids_filename)
    except FileNotFoundError:
        logging.warning(f"skipping {nifti_name}, file not found")
    return bids


def days_list(n_days_to_check):
    now = arrow.now()
    to_check = []
    for days_ago in range(n_days_to_check):
        d = now.shift(days=-days_ago).format("YYYYMMDD")
        to_check.append(d)
    return to_check


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run check if study directories need QC processing."
    )
    parser.add_argument(
        "--dry-run",
        help="Don't actually run the MRIQC. Still does the copying though!",
        action="store_true",
    )
    parser.add_argument(
        "--force",
        help="Run even if HTML files exist.",
        action="store_true",
    )
    how_to_look = parser.add_mutually_exclusive_group(required=True)
    how_to_look.add_argument(
        "--days", help="Number of days ago to start looking for studies.", type=int
    )
    how_to_look.add_argument(
        "--folder",
        nargs="+",
        help="Exact folder name to process.",
    )

    args = parser.parse_args()

    logging.info("Starting daily_qc_p1")

    runs = []
    if args.days:
        runs = [match[0] for match in (glob(f"/qc/dicom-in/{d}_????_Prisma") for d in days_list(args.days)) if match]

    if args.folder:
        runs = args.folder


    for run in runs:
        # run is a FOLDER now
        foldername = Path(run).name
        outfolder = f"{root_out}/{foldername}"
        logging.info(f"output folder: {outfolder}")
        Path(outfolder).mkdir(parents=True, exist_ok=True)

        if glob(f"{outfolder}/*html") and not args.force:
            logging.info(f"HTML files already in {outfolder}, skipping {foldername}")
            continue

        bids = f"{root_in}/{foldername}"
        logging.info(f"copying {foldername} to input folder")

        Path(f"{bids}/sub-phantom/func").mkdir(parents=True, exist_ok=True)

        # copy all the niftis
        # we want ep2d_bold_N.nii.gz
        #         epi_mb_N.nii.gz

        to_process = {"ep2d_bold_": "ep2d", "epi_mb_": "mb"}
        for scanname, bids_name in to_process.items():
            niftis = glob(f"{run}/{scanname}*{niigz}")
            nifti_name = final_scan(niftis)
            if not args.dry_run:
                copy_to_in_folder(bids, nifti_name, "phantom", bids_name)

        cmd = (
            f"docker run --user 1001:1001 -v {bids}:/data:ro -v {outfolder}:/out nipreps/mriqc:latest "
            f"/data /out participant --no-sub "
        )

        if not args.dry_run:
            logging.info(f"Running {cmd}")
            subprocess.run(cmd.split())

            logging.info("Done running MRIQC. Copying json files to longitudinal.")
            Path(f"{root_out}/longitudinal/QA").mkdir(
                parents=True, exist_ok=True
            )
            for src in glob(f"{outfolder}/sub-phantom/func/*json"):
                dst = f"{root_out}/longitudinal/QA/{foldername}_{Path(src).name}"
                logging.info(f"copy {src} to {dst}")
                copyfile(src, dst)
        else:
            logging.info(f"Would run {cmd}")

    logging.info("Ending daily_qc_p1")
