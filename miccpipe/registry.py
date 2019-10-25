import yaml
from os.path import join as pjoin
from pathlib import Path
import sys

DICOMIN = "/data/pipeline"
SDFNAME = "STUDY_DESCRIPTION"


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def registry_info(studydir):
    REGISTRY_FILE = pjoin(DICOMIN, "registry.yml")
    registry = yaml.safe_load(open(REGISTRY_FILE))

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
