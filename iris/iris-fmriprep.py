#!/cm/shared/anaconda3/envs/iris/bin/python

import re
import os
from collections import defaultdict
from preprocess import preprocess
import subprocess
import shutil
from glob import glob
import yaml
import logging
import argparse
from os.path import join as pjoin
from nipype.interfaces.dcm2nii import Dcm2niix
from deface import deface_t1, deface_t2
from converters import convert_to_bids, convert_to_nifti

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)


def task_select(choice):
    tasks = {"ignore": False, "nifti": False, "bids": False, "fmriprep": False}
    if choice in ("ignore",):
        tasks["ignore"] = True
        return tasks

    if choice in ("nifti", "bids", "fmriprep"):
        tasks["nifti"] = True
    if choice in ("bids", "fmriprep"):
        tasks["bids"] = True
    if choice in ("fmriprep",):
        tasks["fmriprep"] = True
    return tasks


def submit_fmriprep(config, studydir, subject):
    logging.info("running fmriprep")
    args = defaultdict(bool, config.get("fmriprep", {}))
    workdir = config["workdir"]

    # build the command line rather than call, because it does
    # a bunch of work in main I don't want to re-implement.

    s = []
    s += ["/cm/shared/anaconda3/envs/iris/bin/python3"]
    s += ["/home/ddrucker/mictools/micc_fmriprep.py"]
    s += ["--bidsdir", studydir]
    s += [
        "--workdir",
        pjoin(workdir, os.path.basename(studydir)),
    ]
    s += ["--participant", subject]

    for arg in (
        "anat-only",
        "aroma",
        "dry-run",
        "freesurfer",
        "longitudinal",
        "return-all-components",
    ):
        if args[arg]:
            s += ["--" + arg]
    for arg in (
        "dummy-scans",
        "fmriprep-version",
        "ignore",
        "ncpus",
        "output-spaces",
        "ramsize",
    ):
        if args[arg]:
            s += ["--" + arg, str(args[arg])]

    logging.info("Running command: " + " ".join(s))

    proc = subprocess.Popen(s, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, stderr = proc.communicate()
    if b"has been submitted" in stdout:
        job_id = re.search(r"Your job (\d{6})", str(stdout)).group(1)
        logging.info(f"Submitted job {job_id} to SGE")
        open(pjoin(studydir, ".sgejobid"), "w").write(job_id)
    else:
        logging.warning(
            f"Something went wrong submitting to the queue:\nSTDOUT:\n{stdout}STDERR:\n{stderr}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Submit an iris-got study to fmriprep."
    )
    parser.add_argument(
        "--config", "-c", required=True, help="Path to YAML config file."
    )
    parser.add_argument("--subject", "-s", required=True, help="Subject number.")
    parser.add_argument(
        "--session", "-e", help="Session number (optional).", default=None
    )
    parser.add_argument(
        "studydir", help="Path to study received from Iris (dicom dir)."
    )
    args = parser.parse_args()

    config = yaml.safe_load(open(args.config))
    tasks = task_select(config["run"])

    if tasks["ignore"]:
        logging.warning("Task was set to ignore; doing nothing.")
        sys.exit(1)

    if tasks["nifti"]:
        logging.info("Converting to nifti")
        convert_to_nifti(args.studydir)
    if tasks["bids"]:
        logging.info("Organizing in BIDS format")
        convert_to_bids(config, args.studydir, args.subject, args.session)
    if tasks["fmriprep"]:
        submit_fmriprep(config, args.studydir, args.subject)
