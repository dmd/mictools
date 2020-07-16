import yaml
from os.path import join as pjoin
from pathlib import Path
import sys
from glob import glob
import re
import receiver_eostudy
import logging

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)

DICOMIN = "/data/pipeline"
EOSTUDY_TIMEOUT = 60


def condensed_name(s):
    return re.sub(r"[^A-Z0-9]", "", s.upper())


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


def registry_info(studydir):
    rawregistry = {}
    registry = {}

    for _ in glob(pjoin(DICOMIN, "registry") + "/*.yaml"):
        try:
            rawregistry.update(yaml.safe_load(open(_)))
        except:
            logging.warning(f"Failed to load {_}, continuing without it.")
            continue

    # condense to alphanumeric
    for k in rawregistry:
        registry[condensed_name(k)] = rawregistry[k]

    # resolve aliases
    aliased = [sd for sd in registry if "alias" in registry[sd]]
    for sd in aliased:
        target = condensed_name(registry[sd]["alias"])
        if target in registry:
            registry[sd] = registry[target]

    if Path(DICOMIN) not in Path(studydir).resolve().parents:
        logging.critical(f"STUDYDIR {studydir} needs to be within DICOMIN {DICOMIN}")
        raise RuntimeError

    StudyDescription = receiver_eostudy.metadata(studydir)["StudyDescription"]
    ReferringPhysicianName = receiver_eostudy.metadata(studydir).get(
        "ReferringPhysicianName", "NA"
    )

    config = dict(registry["DEFAULT"])
    if "RPN" + condensed_name(ReferringPhysicianName) in registry:
        config.update(registry["RPN" + condensed_name(ReferringPhysicianName)])
    elif condensed_name(StudyDescription) in registry:
        config.update(registry[condensed_name(StudyDescription)])
    else:
        logging.warning(
            f"neither RPN{ReferringPhysicianName} nor {StudyDescription} found in registry"
        )
        raise KeyError

    return config
