import yaml
from os.path import join as pjoin
from pathlib import Path
import sys
from glob import glob
import receiver_eostudy

DICOMIN = "/data/pipeline"


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def registry_info(studydir):
    registry = {}
    for _ in glob(pjoin(DICOMIN, "registry") + "/*.yaml"):
        registry.update(yaml.safe_load(open(_)))

    if Path(DICOMIN) not in Path(studydir).resolve().parents:
        eprint(f"STUDYDIR {studydir} needs to be within DICOMIN {DICOMIN}")
        sys.exit(1)

    StudyDescription = receiver_eostudy.metadata(studydir)["StudyDescription"]

    if StudyDescription not in registry:
        eprint(f"{StudyDescription} not found in registry")
        sys.exit(1)

    config = dict(registry["DEFAULT"])
    config.update(registry[StudyDescription])

    return config
