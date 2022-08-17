import yaml
from pprint import pprint
import re


def match_from_list(possibles, match):
    for p in possibles:
        if re.search(p, match, re.IGNORECASE):
            return True
    return False


class Studypar:
    def __init__(self, studypar_file, qctypes_file="qctypes.yaml"):
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

    def matches(self):
        for qctype, qcdict in self.qctypes.items():
            if match_from_list(qcdict["name"], self["name"]) and match_from_list(
                qcdict["samplename"], self["samplename"]
            ):
                return {
                    "folder": qctype,
                    "ident": self["ident"],
                    "emails": qcdict["emails"],
                }


if __name__ == "__main__":
    studypar_file = "../tests/qc_mriqc/studypar.Bergman.ss25m.THC-fMRI"
    f = Studypar(studypar_file)
    pprint(f.matches())
