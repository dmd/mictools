import yaml
from pathlib import Path
import re


qctypes_file = Path(__file__).parent / "qctypes.yaml"


def match_from_list(possibles, match):
    for p in possibles:
        if re.search(p, match, re.IGNORECASE):
            return True
    return False


class Studypar:
    def __init__(self, studypar_file, qctypes_file=qctypes_file):
        self.studypar_file = studypar_file
        self.qctypes = yaml.safe_load(open(qctypes_file))

    def __getitem__(self, item):
        """
        Get the value of a key from the studypar file.
        """
        with open(self.studypar_file, "r") as f:
            for line in f:
                if line.startswith(item):
                    # get subsequent line
                    line = next(f)
                    return line.split(" ", 1)[1].replace('"', "").strip()

    def info(self):
        for qctype, qcdict in self.qctypes.items():
            if match_from_list(qcdict["name"], self["name"]) and match_from_list(
                qcdict["samplename"], self["samplename"]
            ):
                return {
                    "folder": qctype,
                    "ident": self["ident"],
                    "emails": qcdict.get("emails", []),
                    "niftis": qcdict.get("niftis", []),
                }
