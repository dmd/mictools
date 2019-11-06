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
    studydir = sys.argv[1]
    ds = pydicom.dcmread(glob(pjoin(studydir, "MR*"))[0])

    config = configparser.ConfigParser()
    config["dicom"] = {}
    config["dicom"]["StudyDescription"] = ds.StudyDescription
    config["dicom"]["StudyInstanceUID"] = ds.StudyInstanceUID
    config["dicom"]["StudyDateTime"] = datetime.strptime(
        ds.StudyDate + ds.StudyTime, "%Y%m%d%H%M%S.%f"
    ).strftime("%Y-%m-%d %H:%M")
    config["dicom"]["AccessionNumber"] = ds.AccessionNumber

    config.write(open(pjoin(studydir, SMDNAME), "w"))
    open(pjoin(studydir, ".pipe_ready"), "w").write("")
