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
import numpy
import hashlib
import requests
from tempfile import NamedTemporaryFile
from registry import DICOMIN, registry_info, task_select
from receiver_eostudy import SMDNAME, metadata
from sub_ses_matcher import send_form_email, sheet_lookup

SSH_COMMAND = "ssh -i /pipeline.ssh/id_ecdsa -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no pipeline@micc".split()


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

    if os.environ.get("INSIDE_DOCKER", False) == "yes":
        real_DICOMIN = os.environ["REAL_DICOMIN"]
        real_studydir = studydir.replace(DICOMIN, real_DICOMIN)
    else:
        real_DICOMIN = DICOMIN
        real_studydir = studydir

    # build the command line rather than call, because it does
    # a bunch of work in main I don't want to re-implement.

    s = []
    s += ["/cm/shared/anaconda3/envs/rapidtide/bin/python3"]
    s += ["/home/ddrucker/mictools/micc_fmriprep.py"]

    s += ["--bidsdir", real_studydir]
    s += [
        "--workdir",
        pjoin(real_DICOMIN, "fmriprep-working", os.path.basename(studydir)),
    ]
    s += ["--participant", subject]

    for arg in ("aroma", "freesurfer", "anat-only", "dry-run"):
        if args[arg]:
            s += ["--" + arg]
    for arg in ("ncpus", "ramsize", "output-spaces", "ignore"):
        if args[arg]:
            s += ["--" + arg, str(args[arg])]

    print(f"{colors.OK}Running command: " + " ".join(s) + f"{colors.END}")

    if os.environ.get("INSIDE_DOCKER", False) == "yes":
        # submit via ssh
        print("Submitting job via ssh")
        s = SSH_COMMAND + s
        print(s)

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
    niftidir = pjoin(studydir, "nifti")
    dicomdir = pjoin(studydir, "dicom")
    os.mkdir(niftidir)
    dcm = Dcm2niix()
    dcm.inputs.source_dir = dicomdir
    dcm.inputs.output_dir = niftidir
    dcm.inputs.out_filename = "%d_%s"
    dcm.run()


def convert_to_bids(studydir, subject, session=None):
    EXTENSIONS = (".json", ".bval", ".bvec", ".tsv", ".nii.gz")
    sourcedata_dir = pjoin(studydir, "sourcedata", "sub-" + subject)
    subject_dir = pjoin(studydir, "sub-" + subject)

    if session:
        sourcedata_dir = pjoin(sourcedata_dir, "ses-" + session)
        subject_dir = pjoin(subject_dir, "ses-" + session)

    # make a totally generic bids folder
    os.makedirs(sourcedata_dir)
    os.makedirs(subject_dir)

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

    # move data into sourcedata
    for _ in ("nifti", "dicom"):
        shutil.move(pjoin(studydir, _), sourcedata_dir)

    niftidir = pjoin(sourcedata_dir, "nifti")

    bidsnames = registry_info(studydir)["bidsnames"]
    for scantype in bidsnames:  # ('anat', 'func')
        scantype_dir = pjoin(subject_dir, scantype)
        os.mkdir(scantype_dir)
        for scanname in bidsnames[scantype]:
            # take only the latest; exclude _ph.nii.gz phase component
            scans = [
                os.path.basename(_)
                for _ in glob(pjoin(niftidir, scanname + "*[0-9].nii.gz"))
            ]
            if not scans:
                print(f"{colors.WARN}No scans found named {scanname}.{colors.END}")
                continue
            source = final_scan(scans)
            basename = f"sub-{subject}_"
            if session:
                basename += f"ses-{session}_"
            basename += bidsnames[scantype][scanname]
            shutil.copyfile(
                pjoin(niftidir, source), pjoin(scantype_dir, basename + ".nii.gz")
            )
            print(f"{colors.OK}Copying {source} to {basename}.")
            for extension in EXTENSIONS:
                try:
                    shutil.copyfile(
                        pjoin(niftidir, source.replace(".nii.gz", extension)),
                        pjoin(scantype_dir, basename + extension),
                    )
                except FileNotFoundError:
                    pass


def main():
    ready_dirs = Path(DICOMIN).glob("*/.pipe_ready")
    for ready_dir in ready_dirs:
        studydir = str(ready_dir.parent)
        try:
            tasks = task_select(registry_info(studydir)["run"])
        except (RuntimeError, KeyError):
            continue
        AccessionNumber = metadata(studydir)["AccessionNumber"]
        subject, session = sheet_lookup(AccessionNumber)
        if subject:
            # don't send email if it's already there
            open(pjoin(studydir, ".pipe_emailsent"), "a").write("")
        if tasks["bids"]:
            if not os.path.exists(pjoin(studydir, ".pipe_emailsent")):
                send_form_email(studydir)
                print(
                    f"{colors.OK}Sending AccessionNumber form email request.{colors.END}"
                )
                print(
                    f"{colors.WARN}Can't do any more work without that, so skipping.{colors.END}"
                )
                continue
            if not subject:
                print(
                    f"{colors.WARN}Didn't find {AccessionNumber} in sheet yet. Skipping.{colors.END}"
                )
                continue

        os.remove(pjoin(studydir, ".pipe_ready"))
        print(f"{colors.HEADER}START processing {studydir}{colors.END}")

        if tasks["nifti"]:
            print(f"{colors.OK}Converting to nifti{colors.END}")
            convert_to_nifti(studydir)
        if tasks["bids"]:
            print(f"{colors.OK}Organizing in BIDS format{colors.END}")
            convert_to_bids(studydir, subject, session)
        if tasks["fmriprep"]:
            submit_fmriprep(studydir, subject)
        print(f"{colors.HEADER}END {studydir}{colors.END}\n\n")
        open(pjoin(studydir, ".pipe_complete"), "a").close()
    if not list(ready_dirs):
        print(f"{colors.OK}Nothing left to do.{colors.END}")


if __name__ == "__main__":
    main()
