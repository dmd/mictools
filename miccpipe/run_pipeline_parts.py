#!/usr/bin/env python

import os
from os.path import join as pjoin
from pathlib import Path
from glob import glob
from collections import defaultdict
from time import sleep
import subprocess
import shutil
from nipype.interfaces.dcm2nii import Dcm2niix
from registry import DICOMIN, SDFNAME, registry_info


class colors:
    HEADER = "\033[95m"
    OK = "\033[93m"
    WARN = "\033[93m"
    END = "\033[0m"


def final_scan(sourcenames):
    # given ['FOO_BAR_11.nii.gz', 'FOO_BAR_2.nii.gz', 'FOO_BAR_3.nii.gz']
    # return 'FOO_BAR_11.nii.gz', the highest numbered scan

    return sorted(
        sourcenames, key=lambda x: int(x.replace(".nii.gz", "").rsplit("_", 1)[-1])
    )[-1]


def submit_fmriprep(studydir):
    print(f"{colors.OK}│      running fmriprep{colors.END}")
    args = defaultdict(bool, registry_info(studydir).get("fmriprep", {}))

    # build the command line rather than call, because it does
    # a bunch of work in main I don't want to re-implement.

    s = []
    s += ["/home/ddrucker/mictools/micc_fmriprep.py"]

    s += ["--bidsdir", studydir]
    s += ["--workdir", pjoin(DICOMIN, "fmriprep-working", os.path.basename(studydir))]
    s += ["--participant", "XXXX"]

    if args["aroma"]:
        s += ["--aroma"]
    if args["ncpus"]:
        s += ["--ncpus", str(args["ncpus"])]
    if args["ramsize"]:
        s += ["--ramsize", str(args["ramsize"])]
    if args["freesurfer"]:
        s += ["--freesurfer"]
    if args["anat-only"]:
        s += ["--anat-only"]
    if args["output-spaces"]:
        s += ["--output-spaces", args["output-spaces"]]
    if args["dry-run"]:
        s += ["--dry-run"]

    print(f"{colors.OK}│      running: " + " ".join(s) + f"{colors.END}")
    subprocess.call(s)


def convert_to_nifti(studydir):
    niftidir = str(studydir) + "_nifti"
    os.mkdir(niftidir)
    dcm = Dcm2niix()
    dcm.inputs.source_dir = studydir
    dcm.inputs.output_dir = niftidir
    dcm.inputs.out_filename = "%d_%s"
    dcm.run()
    shutil.copyfile(pjoin(studydir, SDFNAME), pjoin(niftidir, SDFNAME))
    shutil.rmtree(studydir)
    os.rename(niftidir, studydir)


def convert_to_bids(studydir, subject="sub-XXXX"):
    sourcedata_dir = pjoin(studydir, "sourcedata", subject)
    subject_dir = pjoin(studydir, subject)

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
    open(pjoin(studydir, ".bidsignore"), "w").write("STUDY_DESCRIPTION\n.pipe*\n")

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
            basename = subject + "_" + bidsnames[scantype][scanname]
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
    print("scanning for .pipeready ...")
    while True:
        for ready_dir in Path(DICOMIN).glob("*/.pipeready"):
            studydir = str(ready_dir.parent)
            reg_info = registry_info(studydir)
            os.remove(pjoin(studydir, ".pipeready"))
            print(f"{colors.HEADER}┌───── start {studydir}{colors.END}")
            tasks = task_select(reg_info["run"])
            if tasks["nifti"]:
                print(f"{colors.OK}│      Converting to nifti{colors.END}")
                convert_to_nifti(studydir)
            if tasks["bids"]:
                print(f"{colors.OK}│      Organizing in BIDS format{colors.END}")
                convert_to_bids(studydir)
            if tasks["fmriprep"]:
                submit_fmriprep(studydir)
            print(f"\033[95m└───── end   {studydir}\n")
            open(pjoin(studydir, ".pipecomplete"), "a").close()
        sleep(5)


if __name__ == "__main__":
    main()
