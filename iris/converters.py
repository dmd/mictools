from glob import glob
import shutil
import logging
import os
from os.path import join as pjoin
from nipype.interfaces.dcm2nii import Dcm2niix
import re
from preprocess import preprocess

niigz = ".nii.gz"


def final_scan(sourcenames, multiecho=False):
    # if single-echo:
    #  given ['FOO_BAR_11.nii.gz', 'FOO_BAR_2.nii.gz', 'FOO_BAR_3.nii.gz']
    #  return 'FOO_BAR_11.nii.gz', the highest numbered scan
    # if multi-echo
    #  given:
    #   ['checkerboard_AP_SBRef_37_e1.nii.gz',
    #   'checkerboard_AP_SBRef_37_e2.nii.gz',
    #   'checkerboard_AP_SBRef_37_e3.nii.gz',
    #   'checkerboard_AP_SBRef_38_e1.nii.gz',
    #   'checkerboard_AP_SBRef_38_e2.nii.gz',
    #   'checkerboard_AP_SBRef_38_e3.nii.gz']
    #
    #  return:
    #   ['checkerboard_AP_SBRef_38_e1.nii.gz',
    #   'checkerboard_AP_SBRef_38_e2.nii.gz',
    #   'checkerboard_AP_SBRef_38_e3.nii.gz']

    if not sourcenames:
        return []

    files = {}
    for file in sourcenames:

        if multiecho:
            m = re.search(rf"_(\d+)_e\d{niigz}$", file)
            fid = int(m.group(1))
        else:
            m = re.search(rf"_(\d+){niigz}$", file)
            fid = int(m.group(1))

        if fid not in files:
            files[fid] = []
        files[fid].append(file)

    ids = sorted(list(files.keys()))

    return sorted(files[ids[-1]])


def convert_to_nifti(studydir):
    logging.info("Converting to nifti")
    dicomdir = pjoin(studydir, "scans")
    niftidir = pjoin(studydir, "nifti")
    os.mkdir(niftidir)
    dcm = Dcm2niix()
    dcm.ignore_exception = True
    dcm.inputs.source_dir = dicomdir
    dcm.inputs.output_dir = niftidir
    dcm.inputs.out_filename = "%d_%s"
    dcm.run()


def convert_to_bids(config, studydir, subject, session):
    logging.info("Organizing in BIDS format")
    EXTENSIONS = (".json", ".bval", ".bvec", ".tsv", niigz)
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
    open(pjoin(studydir, ".bidsignore"), "w").write(".sge*\n.task*\n")

    # move data into sourcedata
    for _ in ("nifti", "scans"):
        shutil.move(pjoin(studydir, _), sourcedata_dir)

    niftidir = pjoin(sourcedata_dir, "nifti")

    bidsnames = config["bidsnames"]

    for scantype in bidsnames:  # ('anat', 'func')
        scantype_dir = pjoin(subject_dir, scantype)
        os.mkdir(scantype_dir)
        for scanname, _ in sorted(bidsnames[scantype].items(), key=lambda x: x[1]):
            # take only the latest; exclude _ph.nii.gz phase component
            scans = [
                os.path.basename(_)
                for _ in glob(pjoin(niftidir, scanname + f"*[0-9]{niigz}"))
            ]
            if not scans:
                logging.warning(f"No scans found named {scanname}.")
                continue

            # is this a multi-echo scan?
            multiecho = scans[0].split("_")[-1][0] == "e"

            sources = final_scan(scans, multiecho)

            for source in sources:
                basename = f"sub-{subject}_"
                if session:
                    basename += f"ses-{session}_"
                if multiecho:
                    m = re.search(rf"_\d+_e(\d){niigz}$", source)
                    echonum = m.group(1)
                    basename += f"echo-{echonum}_"

                bidsbase = bidsnames[scantype][scanname]
                basename += bidsbase

                logging.info(f"Copying {source} to {basename}.")
                for extension in EXTENSIONS:
                    try:
                        shutil.copyfile(
                            pjoin(niftidir, source.replace(niigz, extension)),
                            pjoin(scantype_dir, basename + extension),
                        )
                        preprocess(
                            config,
                            studydir,
                            scantype_dir,
                            basename,
                            extension,
                            bidsbase,
                        )
                    except FileNotFoundError:
                        pass
