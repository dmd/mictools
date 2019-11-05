#!/usr/bin/env python3
from glob import glob
import sys
import os
from datetime import datetime
from os.path import join as pjoin
import configparser
import pydicom

SMDNAME = ".STUDY_METADATA"


def metadata(studydir):
    config = configparser.ConfigParser()
    config.read(pjoin(studydir, SMDNAME))
    return config["dicom"]


if __name__ == "__main__":
    os.chdir(sys.argv[1])
    ds = pydicom.dcmread(glob("MR*")[0])

    config = configparser.ConfigParser()
    config["dicom"] = {}
    config["dicom"]["description"] = ds.StudyDescription
    config["dicom"]["uid"] = ds.StudyInstanceUID
    config["dicom"]["dt"] = datetime.strptime(
        ds.StudyDate + ds.StudyTime, "%Y%m%d%H%M%S.%f"
    ).strftime("%Y-%m-%d %H:%M")
    config.write(open(SMDNAME, "w"))

    open(".pipe_ready", "w").write("")
