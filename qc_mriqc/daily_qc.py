#!/usr/bin/env python3

from pathlib import Path
import arrow
from glob import glob
from shutil import copyfile
import subprocess
import argparse
from studypar import Studypar

root_in = "/qc/mriqc/in/94t"
root_out = "/qc/mriqc/out/94t"


def copy_to_in_folder(bids, nifti_name, ident, bids_name):
    Path(f"{bids}/sub-{ident}/func").mkdir(parents=True, exist_ok=True)
    open(f"{bids}/dataset_description.json", "w").write(
        """{"Name": "none","BIDSVersion": "1.2.0","Authors": ["x"]}"""
    )
    bids_filename = f"{bids}/sub-{ident}/func/sub-{ident}_{bids_name}_bold.nii"
    try:
        copyfile(nifti_name, bids_filename)
    except FileNotFoundError:
        print(f"skipping {nifti_name}, file not found")

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

    studypars = []
    if args.days:
        for date in days_list(args.days):
            year = date[:4]
            for studypar in glob(f"/94t/studies_{year}/s_{date}_??/studypar"):
                studypars.append(studypar)

    if args.folder:
        for folder in args.folder:
            for studypar in glob(f"{folder}/studypar"):
                studypars.append(studypar)

    for studypar_file in studypars:
        s = Studypar(studypar_file)
        info = s.info()
        if not info or info["folder"] != "QA":
            continue
        print(info)

        topdir = Path(studypar_file).parent

        outfolder = f"{root_out}/{info['folder']}/{topdir.name}"
        print(f"output folder: {outfolder}")
        Path(outfolder).mkdir(parents=True, exist_ok=True)

        if glob(f"{outfolder}/*html") and not args.force:
            print(f"HTML files already in {outfolder}, skipping {topdir}")
            continue

        bids = f"{root_in}/{info['folder']}/{topdir.name}"
        print(f"copying {topdir.name} to input folder")

        # copy all the niftis requested in the config
        for nii_fileext, bids_name in info["niftis"].items():
            nifti_name = f"{topdir}/mclean_niftis/{topdir.name + nii_fileext}"
            copy_to_in_folder(bids, nifti_name, info["ident"], bids_name)

        cmd = (
            f"docker run -it --user 1001:1001 -v {bids}:/data:ro -v {outfolder}:/out nipreps/mriqc:latest "
            f"/data /out participant --no-sub "
        )

        if args.dry_run:
            print(f"Would run {cmd}")
        else:
            print(f"Running {cmd}")
            # subprocess.run(cmd.split())

            print("Done running MRIQC. Copying json files to longitudinal.")
            Path(f"{root_out}/longitudinal/{info['folder']}").mkdir(
                parents=True, exist_ok=True
            )
            for src in glob(f"{outfolder}/sub-{info['ident']}/func/*json"):
                dst = f"{root_out}/longitudinal/{info['folder']}/{topdir.name}_{Path(src).name}"
                print(f"copy {src} to {dst}")
                copyfile(src, dst)
