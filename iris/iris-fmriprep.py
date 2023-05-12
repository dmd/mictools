#!/cm/shared/anaconda3/envs/iris/bin/python

import argparse
import logging
import os
import sys
import getpass
from os.path import join as pjoin
import re
import subprocess
import yaml
import pprint
from collections import defaultdict

from converters import convert_to_bids, convert_to_nifti

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)

QSUB = "/cm/shared/apps/sge/2011.11p1/bin/linux-x64/qsub"
SBATCH = "/cm/shared/apps/slurm/current/bin/sbatch"
if os.path.isfile(QSUB):
    SYSTYPE = "sge"
    MICC_FMRIPREP = "/home/ddrucker/mictools/micc_fmriprep.py"
    SUB_MATCH = r"Your job (\d{1,7})"
else:
    SYSTYPE = "slurm"
    MICC_FMRIPREP = "/cm/shared/apps/mictools/micc_fmriprep.py"
    SUB_MATCH = r"Submitted batch job (\d{1,7})"


def task_run(task, studydir, write=False):
    taskfile = pjoin(studydir, ".taskrun_" + task)
    if write:
        open(taskfile, "w").write("")
    return os.path.exists(taskfile)


def task_select(choice):
    tasks = {"nifti": False, "bids": False, "fmriprep": False}
    if choice in ("nifti", "bids", "fmriprep"):
        tasks["nifti"] = True
    elif choice == "none":
        logging.error("no run directive found in config")
    else:
        logging.error(f"invalid task '{choice}'")
    if choice in ("bids", "fmriprep"):
        tasks["bids"] = True
    if choice in ("fmriprep",):
        tasks["fmriprep"] = True
    return tasks


def submit_fmriprep(config, studydir, subject):
    logging.info("Submitting fmriprep job to the cluster.")
    args = defaultdict(bool, config.get("fmriprep", {}))
    force_workdir = config.get("force-workdir", False)

    # build the command line rather than call, because it does
    # a bunch of work in main I don't want to re-implement.

    s = []
    s += ["/cm/shared/anaconda3/envs/iris/bin/python3"]
    s += [MICC_FMRIPREP]
    s += ["--bidsdir", studydir]

    if force_workdir:
        s += ["--force-workdir", force_workdir]

    s += ["--participant", subject]

    for arg in (
        "anat-only",
        "aroma",
        "dry-run",
        "freesurfer",
        "longitudinal",
        "me-output-echos",
        "return-all-components",
    ):
        if args[arg]:
            s += ["--" + arg]
    for arg in (
        "anat-derivatives",
        "fmriprep-version",
        "ignore",
        "ncpus",
        "output-spaces",
        "ramsize",
        "topup-max-vols",
    ):
        if args[arg]:
            s += ["--" + arg, str(args[arg])]

    # we need to add dummy-scans even if it's 0 (which above would have been false-y)
    if type(args["dummy-scans"]) is int:
        s += ["--dummy-scans", str(args["dummy-scans"])]

    logging.info("Running command: " + " ".join(s))

    dump = {}

    proc = subprocess.Popen(s, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, stderr = proc.communicate()
    if b"ubmitted" in stdout:
        job_id = re.search(SUB_MATCH, str(stdout)).group(1)
        logging.info(f"Submitted job {job_id} to scheduler")
        open(pjoin(studydir, ".jobid"), "w").write(job_id)
        submitted = True
    else:
        submitted = False
        job_id = -1
        logging.warning(
            f"Something went wrong submitting to the queue:\nSTDOUT:\n{stdout}STDERR:\n{stderr}"
        )

    # write out our debug data
    def qstat_to_dict(rlist):
        return dict(map(lambda s: re.split(": *", s, 1), rlist))

    def scontrol_to_dict(s):
        key_value_pairs = s.split(" ")
        result_dict = {}

        for pair in key_value_pairs:
            if "=" in pair:
                key, value = pair.split("=", 1)
                result_dict[key] = value

        return result_dict

    dump["arguments"] = sys.argv
    dump["cwd"] = os.getcwd()
    dump["user"] = getpass.getuser()
    dump["config"] = config
    dump["studydir"] = studydir
    dump["subject"] = subject
    dump["command"] = " ".join(s)
    dump["submitted"] = submitted
    if submitted:
        dump["jobid"] = job_id

        if SYSTYPE == "sge":
            statcmd = [
                "/cm/shared/apps/sge/2011.11p1/bin/linux-x64/qstat",
                "-j",
                job_id,
            ]
        if SYSTYPE == "slurm":
            statcmd = [
                "/cm/shared/apps/slurm/current/bin/scontrol",
                "-o",
                "show",
                "job",
                job_id,
            ]

        proc = subprocess.Popen(
            statcmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        stdout, stderr = proc.communicate()

        if SYSTYPE == "sge":
            dump["qstat"] = qstat_to_dict(
                [x for x in stdout.decode("ascii").split("\n") if ":" in x]
            )
            dump["submitted_command"] = open(dump["qstat"]["script_file"]).read()
        if SYSTYPE == "slurm":
            dump["scontrol_show_job"] = scontrol_to_dict(stdout.decode("ascii"))
            dump["submitted_command"] = open(
                dump["scontrol_show_job"]["Command"]
            ).read()

    fp = open(f"/data/fmriprep-workdir/logs/{getpass.getuser()}.{job_id}", "w")
    pp = pprint.PrettyPrinter(stream=fp)
    pp.pprint(dump)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""Submit an iris-got study to fmriprep.
iris-fmriprep is expecting a directory with a single directory inside named scans, inside which are the DICOM files."""
    )
    required = parser.add_argument_group("required arguments")
    required.add_argument(
        "--config",
        "-c",
        required=True,
        help="Path to YAML config file.",
    )
    required.add_argument("--subject", "-s", required=True, help="Subject number.")
    parser.add_argument("--session", "-e", help="Session number.", default=None)
    required.add_argument(
        "studydir", help="Path to study received from Iris (dicom dir)."
    )
    args = parser.parse_args()

    config = yaml.safe_load(open(args.config))
    tasks = task_select(config.get("run", "none"))

    if tasks["nifti"] and not task_run("nifti", args.studydir):
        convert_to_nifti(args.studydir)
        task_run("nifti", args.studydir, write=True)
    if tasks["bids"] and not task_run("bids", args.studydir):
        convert_to_bids(config, args.studydir, args.subject, args.session)
        task_run("bids", args.studydir, write=True)
    if tasks["fmriprep"]:
        submit_fmriprep(config, args.studydir, args.subject)
