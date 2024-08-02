#!/cm/shared/apps/miniforge3/envs/iris/bin/python

import argparse
import getpass
import os
import subprocess
import sys

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

failed = False

for accessionnumber in args.accessionnumber:
    if args.flat:
        dlformat = "flat"
        outdir = accessionnumber
    print(f"Fetching {accessionnumber}...")
    cmd = [
        "/cm/shared/apps/miniforge3/envs/iris/bin/ArcGet.py",
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
    cp = subprocess.run(
        args=cmd,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(
            os.environ,
            XNAT_PASS=password,
            XNAT_USER=args.username,
            XNAT_HOST="https://iris.mclean.harvard.edu",
        ),
    )
    if cp.returncode != 0:
        print("ArcGet.py call failed: " + cp.stderr.split("\n")[-2])

        if "401" in cp.stderr:
            print(
                "\n\033[1m * \n * Your Iris username or password is incorrect.\n *\n\033[0m"
            )
            # exit immediately, no sense in trying any more of them
            sys.exit(1)

        if "NoExperimentsError" in cp.stderr:
            # defer exiting, perhaps only some of several are bad
            failed = True
            print(
                f"\n\033[1m * \n * The accession number {accessionnumber} you requested was not found\n * or is not available to you.\n *\n\033[0m"
            )

if failed:
    sys.exit(1)
