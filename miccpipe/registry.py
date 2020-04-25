import yaml
from os.path import join as pjoin
from pathlib import Path
import sys
from glob import glob
import re
import receiver_eostudy

DICOMIN = "/data/pipeline"
EOSTUDY_TIMEOUT = 60


class colors:
    HEADER = "\033[95m"
    OK = "\033[94m"
    WARN = "\033[93m"
    END = "\033[0m"
    FAIL = "\033[91m"


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


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def cprint(color, *args, **kwargs):
    print(color, end="")
    print(*args, **kwargs, end="")
    print(colors.END, flush=True)


def registry_info(studydir):
    rawregistry = {}
    registry = {}

    for _ in glob(pjoin(DICOMIN, "registry") + "/*.yaml"):
        try:
            rawregistry.update(yaml.safe_load(open(_)))
        except:
            eprint(f"Failed to load {_}, continuing without it.")
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
        eprint(f"STUDYDIR {studydir} needs to be within DICOMIN {DICOMIN}")
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
        eprint(
            f"neither RPN{ReferringPhysicianName} nor {StudyDescription} found in registry"
        )
        raise KeyError

    return config
