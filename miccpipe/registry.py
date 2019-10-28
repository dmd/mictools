import yaml
from os.path import join as pjoin
from pathlib import Path
import sys
from glob import glob

DICOMIN = "/data/pipeline"
SDFNAME = "STUDY_DESCRIPTION"


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def registry_info(studydir):
    registry = {}
    for _ in glob(pjoin(DICOMIN, "registry") + "/*.yaml"):
        registry.update(yaml.safe_load(open(_)))

    if Path(DICOMIN) not in Path(studydir).resolve().parents:
        eprint(f"STUDYDIR {studydir} needs to be within DICOMIN {DICOMIN}")
        sys.exit(1)

    STUDY_DESCRIPTION_FILE = pjoin(studydir, SDFNAME)
    studydescription = open(STUDY_DESCRIPTION_FILE).read().rstrip()

    if studydescription not in registry:
        eprint(f"{studydescription} not found in registry")
        sys.exit(1)

    config = dict(registry["DEFAULT"])
    config.update(registry[studydescription])

    return config
