#!/usr/bin/env python3
from glob import glob
import sys
import os
from os.path import join as pjoin
from pathlib import Path
import shutil
import pydicom
from datetime import datetime
from nipype.interfaces.dcm2nii import Dcm2niix


def convert_to_nifti(studydir, newdir):
    niftidir = str(studydir) + "_nifti"
    os.mkdir(niftidir)
    dcm = Dcm2niix()
    dcm.inputs.source_dir = studydir
    dcm.inputs.output_dir = niftidir
    dcm.inputs.out_filename = "%d_%s"
    dcm.run()
    shutil.rmtree(studydir)
    if os.path.exists(newdir):
        if os.path.exists(newdir + ".old"):
            shutil.rmtree(newdir + ".old", ignore_errors=True)
        os.rename(newdir, newdir + ".old")
    os.rename(niftidir, newdir)

if __name__ == "__main__":
    studydir = sys.argv[1]
    studydir_parent = Path(studydir).parent
    ds = pydicom.dcmread(glob(pjoin(studydir, "MR*"))[0])
    dt = datetime.strptime(ds.StudyDate + ds.StudyTime, "%Y%m%d%H%M%S.%f").strftime("%Y%m%d_%H%M")
    newdir = Path(studydir).parent.joinpath(dt + '_' + ds.ManufacturerModelName)
    convert_to_nifti(studydir, newdir)
    open(pjoin(newdir, ".pipe_ready"), "w").write("")
