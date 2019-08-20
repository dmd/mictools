#!/usr/bin/env python3
import os
import sys
import argparse
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
    dashloc = sourcename.find('_', -3, -1)
    if suffix is None:
        destname = sourcename[0:dashloc]
    else:
        destname = sourcename[0:dashloc + 1] + suffix
    if os.path.isdir(destname):
        print('destination directory already exists - skipping')
    else:
        print('moving', sourcename, 'to', destname)
        os.rename(sourcename, destname)


def final_scan(sourcenames):
    # given ['FOO_BAR_BAZ_11', 'FOO_BAR_BAZ_2']
    # return ('FOO_BAR_BAZ_11', 'FOO_BAR_BAZ')
    # i.e., the unnumbered basename, and the highest valued dicomdir

    source = sorted(sourcenames, key=lambda x: int(x.rsplit('_', 1)[-1]))[-1]
    dest = source.rsplit('_', 1)[0]
    return dest, source


def convertdicoms(subjectdir, dicomsubdir, niftisubdir, niftiname):
    sourcedir = pjoin('sourcedata', subjectdir, dicomsubdir)
    if os.path.isdir(sourcedir):
        destdir = pjoin(subjectdir, niftisubdir)
        os.makedirs(destdir, exist_ok=True)
        silentremove(niftiname + '.nii.gz')
        silentremove(niftiname + '.json')
        print(sourcedir, destdir, niftiname)
        dcm2niicmd = ['dcm2niix', '-b', 'y', '-z', 'y', '-f', niftiname, '-o', destdir, sourcedir]
        subprocess.call(dcm2niicmd)
    else:
        print(sourcedir, 'does not exist - skipping')


def create_bids():
    dd = """{
"Name": "Your Study Title",
"BIDSVersion": "1.2.0",
"Authors": ["Your Name"],
"Funding": "Your Funding Source"
}
"""
    open('README', 'a').close()
    open('CHANGES', 'a').close()
    if not os.path.exists('dataset_description.json'):
        with open('dataset_description.json', 'w') as f:
            f.write(dd)


if __name__ == '__main__':
    def is_file_or_dir(arg):
        if not os.path.exists(arg):
            raise argparse.ArgumentTypeError(f'{arg} does not exist')
        else:
            return arg

    parser = argparse.ArgumentParser(description='Convert dicoms from the scanner to BIDS format, using a config file. '
                                                 'You should run this from the top level of a BIDS directory. '
                                                 'Your dicoms should be in ./sourcedata/SUBJECTDIR.')

    mug = parser.add_mutually_exclusive_group(required=True)

    mug.add_argument('--subjectdir',
                     type=is_file_or_dir,
                     help='SUBJECTDIR to be processed, to be found under "sourcedata"')

    parser.add_argument('--config',
                        type=is_file_or_dir,
                        help='Name of config file to use. (Default: scantypes.ini)',
                        default='scantypes.ini')

    mug.add_argument('--config-help',
                     help='Print a sample config file and then exit.',
                     action='store_true')

    mug.add_argument('--init-bids',
                     help='Create template README, CHANGES, dataset_description.json files, then exit.',
                     action='store_true')

    args = parser.parse_args()

    if args.config_help:
        print("""
The file should have two sections, prefixed by [anat] and [func]. Within each section,
specify SCAN_NAME_FROM_SCANNER = scan_name_you_want
Do NOT include the last _NN suffix. The last one will be chosen, and others ignored.

E.g.:
[anat]
T1_MEMPRAGE_64ch_RMS = mprage

[func]
resting_mb6_gr2_64ch = resting
cue_mb6_gr2_1 = cue1
cue_mb6_gr2_2 = cue2
cue_mb6_gr2_3 = cue3

        """)
        sys.exit(0)

    if args.init_bids:
        create_bids()
        sys.exit(0)

    subjectdir = args.subjectdir
    config = read_config(args.config)

    # rename
    for scantype in config:  # ('anat', 'func')
        if scantype == 'DEFAULT':  # ignore configparser silliness
            continue

        for scanname in config[scantype]:
            dest, source = final_scan([f for f in os.listdir(pjoin('sourcedata', subjectdir))
                                       if re.search(re.escape(scanname) + r'_[0-9]*$', f)])
            dest = pjoin('sourcedata', subjectdir, dest)
            if os.path.exists(dest):
                print('destination directory already exists - skipping')
            else:
                print(f'linking {source} to {dest}')
                os.symlink(source, dest)

    # convert
    _, subject = os.path.split(subjectdir)
    for scantype in config:  # ('anat', 'func')
        if scantype == 'DEFAULT':  # ignore configparser silliness
            continue

        for scanname in config[scantype]:
            convertdicoms(subjectdir, scanname, scantype, subject + '_' + config[scantype][scanname])
