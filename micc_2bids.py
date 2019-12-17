#!/usr/bin/env python3
import os
import sys
import argparse
from argparse import RawTextHelpFormatter
import re
from os.path import join as pjoin
import subprocess
import errno


def silentremove(filename):
    try:
        os.remove(filename)
    except OSError as e:
        if e.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
            raise


def read_config(configfile):
    import configparser

    config = configparser.ConfigParser(allow_no_value=True)
    config.optionxform = str
    config.read(configfile)
    return config


def movedcmdir(sourcename, suffix):
    dashloc = sourcename.find("_", -3, -1)
    if suffix is None:
        destname = sourcename[0:dashloc]
    else:
        destname = sourcename[0 : dashloc + 1] + suffix
    if os.path.isdir(destname):
        print("destination directory already exists - skipping")
    else:
        print("moving", sourcename, "to", destname)
        os.rename(sourcename, destname)


def final_scan(sourcenames):
    # given ['FOO_BAR_BAZ_11', 'FOO_BAR_BAZ_2']
    # return ('FOO_BAR_BAZ', 'FOO_BAR_BAZ_11')
    # i.e., the unnumbered basename, and the highest valued dicomdir

    if len(sourcenames) == 0:
        return None, None
    source = sorted(sourcenames, key=lambda x: int(x.rsplit("_", 1)[-1]))[-1]
    dest = source.rsplit("_", 1)[0]
    return dest, source


def convertdicoms(sourcedir, destdir, niftiname):
    if os.path.isdir(sourcedir):
        os.makedirs(destdir, exist_ok=True)
        silentremove(niftiname + ".nii.gz")
        silentremove(niftiname + ".json")
        print(sourcedir, destdir, niftiname)
        dcm2niicmd = [
            "dcm2niix",
            "-b",
            "y",
            "-z",
            "y",
            "-w",
            "1",
            "-f",
            niftiname,
            "-o",
            destdir,
            sourcedir,
        ]
        subprocess.call(dcm2niicmd)
    else:
        print(sourcedir, "does not exist - skipping")


def create_bids():
    dd = """{
"Name": "Your Study Title",
"BIDSVersion": "1.2.0",
"Authors": ["Your Name", "Co-author's Name"],
"Funding": "Your Funding Source"
}
"""
    if not os.path.exists("dataset_description.json"):
        with open("dataset_description.json", "w") as f:
            f.write(dd)

    for filename in ("README", "CHANGES"):
        if not os.path.exists(filename):
            with open(filename, "w") as f:
                f.write("\n")

    if not os.path.exists(".bidsignore"):
        with open(".bidsignore", "w") as f:
            f.write("*.ini\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Convert dicoms from the scanner to quasi-BIDS format, using a config file.\n"
            "You should run this from the top level of a BIDS directory.\n"
            "Your dicoms should be in ./sourcedata/DICOMDIR.\n\n"
            'Why "quasi"? Because BIDS is a rather complex set of formats and rules,\n'
            'and this tool is very very simple. If you want "real" BIDS, use one of:\n\n'
            "  * https://github.com/nipy/heudiconv\n"
            "  * https://github.com/cbedetti/Dcm2Bids\n"
            "  * https://github.com/jmtyszka/bidskit\n"
            "  * https://github.com/dangom/dac2bids\n"
        ),
        formatter_class=RawTextHelpFormatter,
    )

    mug = parser.add_mutually_exclusive_group(required=True)

    mug.add_argument(
        "--dicomdir", help="DICOMDIR to be processed, to be found under sourcedata"
    )

    parser.add_argument(
        "--bidsdir", help="BIDSDIR to use for the processed data", default="."
    )

    parser.add_argument(
        "--subject", help="SUBJECT to use for the processed data", default=None
    )

    parser.add_argument(
        "--session",
        help="SESSION to use for the processed data (if not specified, will assume a single session)",
        default=None,
    )

    parser.add_argument(
        "--config",
        help="Name of config file to use. (Default: scantypes.ini)",
        default="scantypes.ini",
    )

    mug.add_argument(
        "--config-help",
        help="Print a sample config file and then exit.",
        action="store_true",
    )

    mug.add_argument(
        "--init-bids",
        help="Create template README, CHANGES, dataset_description.json files, then exit.",
        action="store_true",
    )

    args = parser.parse_args()

    if args.config_help:
        print(
            """
The file should have two sections, prefixed by [anat] and [func]. Within
each section, specify SCAN_NAME_FROM_SCANNER = scan_name_you_want
Do NOT include the last _NN suffix. The last one will be chosen, 
and others ignored.

It is your responsibility to use names that are BIDS-compliant!

E.g.:

[anat]
T1_MEMPRAGE_64ch_RMS = T1w

[func]
resting_mb6_gr2_64ch = task-resting_bold
cue_mb6_gr2_1 = task-cue1_bold
cue_mb6_gr2_2 = task-cue2_bold
cue_mb6_gr2_3 = task-cue3_bold
        """
        )
        sys.exit(0)

    if args.init_bids:
        create_bids()
        sys.exit(0)

    bidsdir = args.bidsdir

    if args.bidsdir is not None:
        if not os.path.exists(args.bidsdir):
            print(f"bidsdir {args.bidsdir} does not exist")
            sys.exit(1)
    else:
        print("bidsdir must be specified")
        sys.exit(1)

    dicomdir = pjoin(bidsdir, "sourcedata", args.dicomdir)

    if not os.path.exists(dicomdir):
        print(f"dicomdir {dicomdir} does not exist")
        sys.exit(1)

    if args.subject is None:
        print(f"must specify a subject number")
        sys.exit(1)

    if not os.path.exists(args.config):
        print(f"config file {args.config} does not exist")
        sys.exit(1)

    subject = args.subject
    session = args.session
    config = read_config(args.config)

    for scantype in config:  # ('anat', 'func')
        if scantype == "DEFAULT":  # ignore configparser silliness
            continue

        for scanname in config[scantype]:
            dest, source = final_scan(
                [
                    f
                    for f in os.listdir(dicomdir)
                    if re.search(re.escape(scanname) + r"_[0-9]*$", f)
                ]
            )
            if dest is None:
                print(config[scantype][scanname], "not found - skipping")
            else:
                if session is None:
                    destroot = pjoin(bidsdir, "sub-" + subject, scantype)
                    destname = "_".join(["sub-" + subject, config[scantype][scanname]])
                else:
                    destroot = pjoin(
                        bidsdir, "sub-" + subject, "ses-" + session, scantype
                    )
                    destname = "_".join(
                        ["sub-" + subject, "ses-" + session, config[scantype][scanname]]
                    )

                convertdicoms(pjoin(dicomdir, source), destroot, destname)
