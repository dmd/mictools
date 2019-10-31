#!/usr/bin/env python

import os
import sys
from os.path import join as pjoin
from pathlib import Path
from glob import glob
import string
import random
from collections import defaultdict
import re
from time import sleep
import subprocess
import shutil
from nipype.interfaces.dcm2nii import Dcm2niix
from registry import DICOMIN, SDFNAME, SDTNAME, registry_info


class colors:
    HEADER = "\033[95m"
    OK = "\033[94m"
    WARN = "\033[93m"
    END = "\033[0m"
    FAIL = "\033[91m"


def final_scan(sourcenames):
    # given ['FOO_BAR_11.nii.gz', 'FOO_BAR_2.nii.gz', 'FOO_BAR_3.nii.gz']
    # return 'FOO_BAR_11.nii.gz', the highest numbered scan

    return sorted(
        sourcenames, key=lambda x: int(x.replace(".nii.gz", "").rsplit("_", 1)[-1])
    )[-1]


def submit_fmriprep(studydir, subject):
    print(f"{colors.OK}│      running fmriprep{colors.END}")
    args = defaultdict(bool, registry_info(studydir).get("fmriprep", {}))

    # build the command line rather than call, because it does
    # a bunch of work in main I don't want to re-implement.

    s = []
    s += ["/cm/shared/anaconda3/envs/rapidtide/bin/python3"]
    s += ["/home/ddrucker/mictools/micc_fmriprep.py"]

    s += ["--bidsdir", studydir]
    s += ["--workdir", pjoin(DICOMIN, "fmriprep-working", os.path.basename(studydir))]
    s += ["--participant", subject]

    for arg in ("aroma", "freesurfer", "anat-only", "dry-run"):
        if args[arg]:
            s += ["--" + arg]
    for arg in ("ncpus", "ramsize", "output-spaces"):
        if args[arg]:
            s += ["--" + arg, str(args[arg])]

    print(f"{colors.OK}Running command: " + " ".join(s) + f"{colors.END}")

    proc = subprocess.Popen(s, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, stderr = proc.communicate()
    if b"has been submitted" in stdout:
        job_id = re.search(r"Your job (\d{6})", str(stdout)).group(1)
        print(f"{colors.OK}Submitted job {job_id} to SGE{colors.END}")
        open(pjoin(studydir, ".pipe_sgejobid"), "w").write(job_id)
    else:
        print(f"{colors.FAIL}Something went wrong submitting to the queue:")
        print(f"STDOUT:\n{stdout}STDERR:\n{stderr}{colors.END}")


def convert_to_nifti(studydir):
    niftidir = str(studydir) + "_nifti"
    os.mkdir(niftidir)
    dcm = Dcm2niix()
    dcm.inputs.source_dir = studydir
    dcm.inputs.output_dir = niftidir
    dcm.inputs.out_filename = "%d_%s"
    dcm.run()
    shutil.copyfile(pjoin(studydir, SDFNAME), pjoin(niftidir, SDFNAME))
    shutil.copyfile(pjoin(studydir, SDTNAME), pjoin(niftidir, SDTNAME))
    shutil.rmtree(studydir)
    os.rename(niftidir, studydir)


def convert_to_bids(studydir, subject):
    sourcedata_dir = pjoin(studydir, "sourcedata", 'sub-' + subject)
    subject_dir = pjoin(studydir, 'sub-' + subject)

    # make a totally generic bids folder
    os.makedirs(sourcedata_dir)
    os.mkdir(subject_dir)

    # move data into sourcedata
    for _ in os.listdir(studydir):
        if _.endswith(".nii.gz") or _.endswith(".json"):
            os.rename(pjoin(studydir, _), pjoin(sourcedata_dir, _))

    open(pjoin(studydir, "dataset_description.json"), "w").write(
        """
        {
            "Name": "none",
            "BIDSVersion": "1.2.0",
            "Authors": ["name1", "name1"],
            "Funding": "mom"
        }
        """
    )
    open(pjoin(studydir, "README"), "w").write("\n")
    open(pjoin(studydir, "CHANGES"), "w").write("\n")
    open(pjoin(studydir, ".bidsignore"), "w").write(".STUDY_*\n.pipe_*\n")

    bidsnames = registry_info(studydir)["bidsnames"]
    for scantype in bidsnames:  # ('anat', 'func')
        scantype_dir = pjoin(subject_dir, scantype)
        os.mkdir(scantype_dir)
        for scanname in bidsnames[scantype]:
            # take only the latest
            scans = [
                os.path.basename(_)
                for _ in glob(pjoin(sourcedata_dir, scanname + "*.nii.gz"))
            ]
            source = final_scan(scans)
            basename = 'sub-' + subject + "_" + bidsnames[scantype][scanname]
            shutil.copyfile(
                pjoin(sourcedata_dir, source), pjoin(scantype_dir, basename + ".nii.gz")
            )
            shutil.copyfile(
                pjoin(sourcedata_dir, source.replace(".nii.gz", ".json")),
                pjoin(scantype_dir, basename + ".json"),
            )


def task_select(choice):
    tasks = {"nifti": False, "bids": False, "fmriprep": False}
    if choice in ("nifti", "bids", "fmriprep"):
        tasks["nifti"] = True
    if choice in ("bids", "fmriprep"):
        tasks["bids"] = True
    if choice in ("fmriprep",):
        tasks["fmriprep"] = True
    return tasks


def main():
    ready_dirs = Path(DICOMIN).glob("*/.pipe_ready")
    for ready_dir in ready_dirs:
        studydir = str(ready_dir.parent)
        reg_info = registry_info(studydir)
        os.remove(pjoin(studydir, ".pipe_ready"))
        print(f"{colors.HEADER}START processing {studydir}{colors.END}")
        tasks = task_select(reg_info["run"])
        subject = ''.join([random.choice(string.ascii_uppercase) for n in range(4)])
        if tasks["nifti"]:
            print(f"{colors.OK}Converting to nifti{colors.END}")
            convert_to_nifti(studydir)
        if tasks["bids"]:
            print(f"{colors.OK}Organizing in BIDS format{colors.END}")
            convert_to_bids(studydir, subject)
        if tasks["fmriprep"]:
            submit_fmriprep(studydir, subject)
        print(f"{colors.HEADER}END {studydir}{colors.END}\n\n")
        open(pjoin(studydir, ".pipe_complete"), "a").close()
    if not list(ready_dirs):
        print(f"{colors.OK}Nothing to do.{colors.END}")


if __name__ == "__main__":
    main()
