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


def prepare_study(studydir):
    ds = pydicom.dcmread(glob(pjoin(studydir, "MR*"))[0])

    config = configparser.ConfigParser()
    config["dicom"] = {}
    config["dicom"]["StudyDescription"] = ds.StudyDescription
    config["dicom"]["StudyInstanceUID"] = ds.StudyInstanceUID
    config["dicom"]["StudyDateTime"] = datetime.strptime(
        ds.StudyDate + ds.StudyTime, "%Y%m%d%H%M%S.%f"
    ).strftime("%Y-%m-%d %H:%M")
    config["dicom"]["AccessionNumber"] = ds.AccessionNumber

    # move files into dicomdir
    dicomdir = pjoin(studydir, "dicom")
    os.rename(studydir, str(studydir) + "_")
    os.mkdir(studydir)
    os.rename(str(studydir) + "_", dicomdir)

    open(pjoin(studydir, ".pipe_ready"), "w").write("")
    config.write(open(pjoin(studydir, SMDNAME), "w"))


if __name__ == "__main__":
    prepare_study(sys.argv[1])
