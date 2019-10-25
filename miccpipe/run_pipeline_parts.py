#!/usr/bin/env python

import os
from os.path import join as pjoin
from pathlib import Path
from glob import glob
import shutil
from nipype.interfaces.dcm2nii import Dcm2niix
from registry import DICOMIN, SDFNAME, registry_info


def final_scan(sourcenames):
    # given ['FOO_BAR_11.nii.gz', 'FOO_BAR_2.nii.gz', 'FOO_BAR_3.nii.gz']
    # return 'FOO_BAR_11.nii.gz', the highest numbered scan

    return sorted(
        sourcenames, key=lambda x: int(x.replace(".nii.gz", "").rsplit("_", 1)[-1])
    )[-1]


def convert_to_nifti(studydir):
    niftidir = str(studydir) + "_nifti"
    os.mkdir(niftidir)
    dcm = Dcm2niix()
    dcm.inputs.source_dir = studydir
    dcm.inputs.output_dir = niftidir
    dcm.inputs.out_filename = "%d_%s"
    dcm.run()
    shutil.copyfile(pjoin(studydir, SDFNAME), pjoin(niftidir, SDFNAME))
    shutil.rmtree(studydir)
    os.rename(niftidir, studydir)


def convert_to_bids(studydir, subject="sub-XXXX"):
    sourcedata_dir = pjoin(studydir, "sourcedata", subject)
    subject_dir = pjoin(studydir, subject)

    # make a totally generic bids folder
    os.makedirs(sourcedata_dir)
    os.mkdir(subject_dir)

    # move data into sourcedata
    for _ in os.listdir(studydir):
        if _.endswith(".nii.gz") or _.endswith(".json"):
            os.rename(pjoin(studydir, _), pjoin(sourcedata_dir, _))

    open(pjoin(studydir, "dataset_description.json"), "w").write(
        """
        {
            "Name": "none",
            "BIDSVersion": "1.2.0",
            "Authors": ["name1", "name1"],
            "Funding": "mom"
        }
        """
    )
    open(pjoin(studydir, "README"), "w").write("\n")
    open(pjoin(studydir, "CHANGES"), "w").write("\n")
    open(pjoin(studydir, ".bidsignore"), "w").write("STUDY_DESCRIPTION\n")

    bidsnames = registry_info(studydir)["bidsnames"]
    for scantype in bidsnames:  # ('anat', 'func')
        scantype_dir = pjoin(subject_dir, scantype)
        os.mkdir(scantype_dir)
        for scanname in bidsnames[scantype]:
            # take only the latest
            scans = [
                os.path.basename(_)
                for _ in glob(pjoin(sourcedata_dir, scanname + "*.nii.gz"))
            ]
            source = final_scan(scans)
            basename = subject + "_" + bidsnames[scantype][scanname]
            shutil.copyfile(
                pjoin(sourcedata_dir, source), pjoin(scantype_dir, basename + ".nii.gz")
            )
            shutil.copyfile(
                pjoin(sourcedata_dir, source.replace(".nii.gz", ".json")),
                pjoin(scantype_dir, basename + ".json"),
            )


def main():
    for ready_dir in Path(DICOMIN).glob("*/.pipeready"):
        studydir = str(ready_dir.parent)
        os.remove(pjoin(studydir, ".pipeready"))
        reg_info = registry_info(studydir)
        print(f"┌───── start {studydir}")
        if reg_info["nifti"]:
            convert_to_nifti(studydir)
        if reg_info["bids"]:
            convert_to_bids(studydir)

        open(pjoin(studydir, ".pipecomplete"), "a").close()
        print(f"└───── end   {studydir}\n")


if __name__ == "__main__":
    main()
