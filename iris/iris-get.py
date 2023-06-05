#!/cm/shared/anaconda3/envs/iris/bin/python

import argparse
import getpass
import os
import subprocess

parser = argparse.ArgumentParser(
    description="Get studies by accession number from Iris."
)
parser.add_argument(
    "-u",
    "--username",
    help="Your Iris username, if different from your current login.",
    required=False,
    default=getpass.getuser(),
)

parser.add_argument(
    "-f",
    "--flat",
    help="Store all dicom files in one folder - not structured by scan.",
    required=False,
    action="store_true",
)

parser.add_argument(
    "--authfile",
    help="Use .xnat_auth file for login.",
    required=False,
    action="store_true",
)

parser.add_argument("accessionnumber", nargs="+")
args = parser.parse_args()

if not args.authfile:
    password = getpass.getpass(f"Iris password for {args.username}: ")
else:
    password = ""

dlformat = "native"
outdir = "."


for accessionnumber in args.accessionnumber:
    if args.flat:
        dlformat = "flat"
        outdir = accessionnumber
    print(f"Fetching {accessionnumber}...")
    cmd = [
            "/cm/shared/anaconda3/envs/iris/bin/ArcGet.py",
            "--in-mem",
            "-f",
            dlformat,
            "-l",
            accessionnumber,
            "-o",
            outdir,
    ]
    if args.authfile:
        cmd.insert(1, "--alias")
        cmd.insert(2, "iris")
    subprocess.call(
        cmd,
        env=dict(
            os.environ,
            XNAT_PASS=password,
            XNAT_USER=args.username,
            XNAT_HOST="https://iris.mclean.harvard.edu",
        ),
    )
