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

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)


def deface_t1(infile, outfile):
    logging.warning("deface called but not implemented")


def deface_t2(infile, outfile, t1anatfile):
    logging.warning("deface called but not implemented")


def final_scan(sourcenames):
    # given ['FOO_BAR_11.nii.gz', 'FOO_BAR_2.nii.gz', 'FOO_BAR_3.nii.gz']
    # return 'FOO_BAR_11.nii.gz', the highest numbered scan

    return sorted(
        sourcenames, key=lambda x: int(x.replace(".nii.gz", "").rsplit("_", 1)[-1])
    )[-1]


def convert_to_nifti(studydir):
    # convert both to nifti and to separated dicom dirs
    dicomdir = pjoin(studydir, "RAW")
    niftidir = pjoin(studydir, "nifti")
    dicomdirsdir = pjoin(studydir, "dicomdirs")
    os.mkdir(niftidir)
    os.mkdir(dicomdirsdir)
    subprocess.call(
        ["/usr/local/bin/dcm2niix", "-r", "y", "-o", dicomdirsdir, dicomdir]
    )
    dcm = Dcm2niix()
    dcm.inputs.source_dir = dicomdir
    dcm.inputs.output_dir = niftidir
    dcm.inputs.out_filename = "%d_%s"
    dcm.run()


def convert_to_bids(config, studydir, subject, session=None):
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
    for _ in ("nifti", "RAW", "dicomdirs"):
        shutil.move(pjoin(studydir, _), sourcedata_dir)

    niftidir = pjoin(sourcedata_dir, "nifti")

    bidsnames = config["bidsnames"]
    deface = config.get("deface", False)

    t1anatfile = ""
    for scantype in bidsnames:  # ('anat', 'func')
        scantype_dir = pjoin(subject_dir, scantype)
        os.mkdir(scantype_dir)
        for scanname, _ in sorted(bidsnames[scantype].items(), key=lambda x: x[1]):
            # take only the latest; exclude _ph.nii.gz phase component
            scans = [
                os.path.basename(_)
                for _ in glob(pjoin(niftidir, scanname + "*[0-9].nii.gz"))
            ]
            if not scans:
                logging.warning(f"No scans found named {scanname}.")
                continue
            source = final_scan(scans)
            basename = f"sub-{subject}_"
            if session:
                basename += f"ses-{session}_"
            bidsbase = bidsnames[scantype][scanname]
            basename += bidsbase
            logging.info(f"Copying {source} to {basename}.")
            for extension in EXTENSIONS:
                try:
                    shutil.copyfile(
                        pjoin(niftidir, source.replace(".nii.gz", extension)),
                        pjoin(scantype_dir, basename + extension),
                    )
                    preprocess(
                        config, studydir, scantype_dir, basename, extension, bidsbase
                    )
                except FileNotFoundError:
                    pass

            # deface if requested
            anatfile = pjoin(scantype_dir, basename) + ".nii.gz"
            if bidsnames[scantype][scanname] == "T1w" and deface:
                logging.info(f"Defacing {anatfile}")
                t1anatfile = anatfile
                deface_t1(anatfile, anatfile)

            if bidsnames[scantype][scanname] == "T2w" and deface and t1anatfile:
                logging.info(f"Defacing {anatfile}")
                deface_t2(anatfile, anatfile, t1anatfile)


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
