#!/usr/bin/env python

import os
from os.path import join as pjoin
from pathlib import Path
import shutil
from nipype.interfaces.dcm2nii import Dcm2niix
from registry import DICOMIN, SDFNAME, registry_info


def convert_to_nifti(studydir):
    niftidir = str(studydir) + "_nifti"
    os.mkdir(niftidir)
    c = Dcm2niix()
    c.inputs.source_dir = studydir
    c.inputs.output_dir = niftidir
    c.inputs.out_filename = "%d_%s"
    c.run()
    shutil.copyfile(pjoin(studydir, SDFNAME), pjoin(niftidir, SDFNAME))
    shutil.rmtree(studydir)
    os.rename(niftidir, studydir)


if __name__ == "__main__":
    for p in Path(DICOMIN).glob("*/.pipeready"):
        studydir = str(p.parent)
        os.remove(pjoin(studydir, ".pipeready"))
        reg_info = registry_info(studydir)
        print(f"┌───── start {studydir}")
        if reg_info["nifti"]:
            convert_to_nifti(studydir)

        open(pjoin(studydir, ".pipecomplete"), "a").close()
        print(f"└───── end   {studydir}\n")
