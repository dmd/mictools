from glob import glob
import shutil
import logging
import os
import subprocess
from os.path import join as pjoin
from nipype.interfaces.dcm2nii import Dcm2niix

from preprocess import preprocess


def final_scan(sourcenames):
    # given ['FOO_BAR_11.nii.gz', 'FOO_BAR_2.nii.gz', 'FOO_BAR_3.nii.gz']
    # return 'FOO_BAR_11.nii.gz', the highest numbered scan

    return sorted(
        sourcenames, key=lambda x: int(x.replace(".nii.gz", "").rsplit("_", 1)[-1])
    )[-1]


def convert_to_nifti(studydir, sort_dicomdirs):
    logging.info("Converting to nifti")
    # convert both to nifti and to separated dicom dirs
    dicomdir = pjoin(studydir, "RAW")
    niftidir = pjoin(studydir, "nifti")
    os.mkdir(niftidir)

    if sort_dicomdirs:
        dicomdirsdir = pjoin(studydir, "dicomdirs")
        os.mkdir(dicomdirsdir)
        subprocess.call(
            ["/usr/local/bin/dcm2niix", "-r", "y", "-o", dicomdirsdir, dicomdir]
        )

    dcm = Dcm2niix()
    dcm.inputs.source_dir = dicomdir
    dcm.inputs.output_dir = niftidir
    dcm.inputs.out_filename = "%d_%s"
    dcm.run()


def convert_to_bids(config, studydir, subject, session, sort_dicomdirs):
    logging.info("Organizing in BIDS format")
    EXTENSIONS = (".json", ".bval", ".bvec", ".tsv", ".nii.gz")
    sourcedata_dir = pjoin(studydir, "sourcedata", "sub-" + subject)
    subject_dir = pjoin(studydir, "sub-" + subject)

    if session:
        sourcedata_dir = pjoin(sourcedata_dir, "ses-" + session)
        subject_dir = pjoin(subject_dir, "ses-" + session)

    # make a totally generic bids folder
    os.makedirs(sourcedata_dir)
    os.makedirs(subject_dir)

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
    open(pjoin(studydir, ".bidsignore"), "w").write(".STUDY_*\n.pipe_*\n.sge*\n.taskrun_*\n")

    # move data into sourcedata
    for _ in ("nifti", "RAW"):
        shutil.move(pjoin(studydir, _), sourcedata_dir)

    if sort_dicomdirs:
        shutil.move(pjoin(studydir, "dicomdirs"), sourcedata_dir)

    niftidir = pjoin(sourcedata_dir, "nifti")

    bidsnames = config["bidsnames"]

    t1anatfile = ""
    for scantype in bidsnames:  # ('anat', 'func')
        scantype_dir = pjoin(subject_dir, scantype)
        os.mkdir(scantype_dir)
        for scanname, _ in sorted(bidsnames[scantype].items(), key=lambda x: x[1]):
            # take only the latest; exclude _ph.nii.gz phase component
            scans = [
                os.path.basename(_)
                for _ in glob(pjoin(niftidir, scanname + "*[0-9].nii.gz"))
            ]
            if not scans:
                logging.warning(f"No scans found named {scanname}.")
                continue
            source = final_scan(scans)
            basename = f"sub-{subject}_"
            if session:
                basename += f"ses-{session}_"
            bidsbase = bidsnames[scantype][scanname]
            basename += bidsbase
            logging.info(f"Copying {source} to {basename}.")
            for extension in EXTENSIONS:
                try:
                    shutil.copyfile(
                        pjoin(niftidir, source.replace(".nii.gz", extension)),
                        pjoin(scantype_dir, basename + extension),
                    )
                    preprocess(
                        config, studydir, scantype_dir, basename, extension, bidsbase
                    )
                except FileNotFoundError:
                    pass