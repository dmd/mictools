#!/usr/bin/env python3

import os
from pathlib import Path
import sys
import arrow
from glob import glob
from shutil import copyfile
import subprocess
import argparse


def copy_to_in_folder(s_id, nii, ident):
    bids = f"/qc/mriqc/in/94t/{s_id}"
    Path(f"{bids}/sub-qc/func").mkdir(parents=True, exist_ok=True)
    open(f"{bids}/dataset_description.json", "w").write(
        """{"Name": "none","BIDSVersion": "1.2.0","Authors": ["x"]}"""
    )
    copyfile(nii, f"{bids}/sub-{ident}/func/sub-{ident}_task-rest_bold.nii")
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
    parser.add_argument("--days",
                        help="Number of days ago to start looking for studies.",
                        type=int)
    parser.add_argument("--folder",
                        help="Exact folder name to process.",
                        )
    args = parser.parse_args()

    if args.days:
        studypars = []
        for date in days_list(args.days):
            year = date[:4]
            for studypar in glob(f"/94t/studies_{year}/s_{date}_??/studypar"):
                studypars.append(studypar)
    print


matching = {}
for date in to_check:
    year = date[:4]
    for studypar in glob(f"/94t/studies_{year}/s_{date}_??/studypar"):
        with open(studypar, "r") as f:
            content = f.readlines()
            if "SiteQA" in content[1]:
                topdir = Path(studypar).parent
                name = topdir.name
                nii = os.path.join(
                    topdir, "mclean_niftis", name + "_epip_qa_middle_01.nii"
                )
                matching[name] = nii

# {'s_20220726_03': '/94t/studies_2022/s_20220726_03/mclean_niftis/s_20220726_03_epip_qa_middle_01.nii'}

for study, nii in matching.items():
    htmlfile = f"/qc/mriqc/out/94t/{study}/sub-qc_task-rest_bold.html"
    if Path(htmlfile).exists():
        print(f"{htmlfile} exists, skipping {study}")
    else:
        print(f"copying {study} to input folder")
        bids = copy_to_in_folder(study, nii)
        outfolder = f"/qc/mriqc/out/94t/{study}"
        Path(outfolder).mkdir(parents=True, exist_ok=True)
        print(f"Starting MRIQC in {bids}, outputting to {outfolder}...")
        subprocess.run(
            [
                "docker",
                "run",
                "-it",
                "--user",
                "1001:1001",
                "-v",
                f"{bids}:/data:ro",
                "-v",
                f"{outfolder}:/out",
                "nipreps/mriqc:latest",
                "/data",
                "/out",
                "participant",
                "--no-sub",
            ]
        )
        print("Done running MRIQC.")
        copyfile(
            f"{outfolder}/sub-qc/func/sub-qc_task-rest_bold.json",
            f"/qc/mriqc/out/94t/longitudinal/{study}.json",
        )
