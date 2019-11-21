import yaml
from os.path import join as pjoin
from pathlib import Path
import sys
from glob import glob
import receiver_eostudy
import re

DICOMIN = "/data/pipeline"


def condensed_name(s):
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def task_select(choice):
    tasks = {"nifti": False, "bids": False, "fmriprep": False}
    if choice in ("nifti", "bids", "fmriprep"):
        tasks["nifti"] = True
    if choice in ("bids", "fmriprep"):
        tasks["bids"] = True
    if choice in ("fmriprep",):
        tasks["fmriprep"] = True
    return tasks


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def registry_info(studydir):
    rawregistry = {}
    registry = {}

    for _ in glob(pjoin(DICOMIN, "registry") + "/*.yaml"):
        rawregistry.update(yaml.safe_load(open(_)))

    # condense to alphanumeric
    for k in rawregistry:
        registry[condensed_name(k)] = rawregistry[k]

    if Path(DICOMIN) not in Path(studydir).resolve().parents:
        eprint(f"STUDYDIR {studydir} needs to be within DICOMIN {DICOMIN}")
        raise RuntimeError

    StudyDescription = receiver_eostudy.metadata(studydir)["StudyDescription"]

    if condensed_name(StudyDescription) not in registry:
        eprint(f"{StudyDescription} not found in registry")
        raise KeyError

    config = dict(registry["DEFAULT"])
    config.update(registry[condensed_name(StudyDescription)])

    return config
