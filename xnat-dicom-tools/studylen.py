#!/usr/bin/env python

import glob
import pydicom
from datetime import datetime, timedelta

files = glob.glob("/input/**/*.dcm", recursive=True)


def series(x):
    return int(x.split("-")[1])


def instance(x):
    return int(x.split("-")[2])


valids = [f for f in files if series(f) < 90]
valids.sort(key=lambda x: (series(x), instance(x)))
final = pydicom.read_file(valids[-1])
slen = datetime.strptime(final.InstanceCreationTime, "%H%M%S.%f") - datetime.strptime(
    final.StudyTime, "%H%M%S.%f"
)
out = str(slen - timedelta(microseconds=slen.microseconds))
with open("/output/study_duration.txt", "w") as fh:
    fh.write(out + "\n")
