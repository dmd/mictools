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
parser.add_argument("accessionnumber", nargs="+")
args = parser.parse_args()

password = getpass.getpass(f"Iris password for {args.username}: ")

for accessionnumber in args.accessionnumber:
    print(f"Fetching {accessionnumber}...")
    subprocess.call(
        ["/cm/shared/anaconda3/envs/iris/bin/ArcGet.py", "-f", "native", "-l", accessionnumber],
        env=dict(
            os.environ,
            XNAT_PASS=password,
            XNAT_USER=args.username,
            XNAT_HOST="https://iris.mclean.harvard.edu",
        ),
    )
