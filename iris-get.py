#!/usr/bin/env python3

import argparse
import os
import getpass

parser = argparse.ArgumentParser(
    description="Get a study by accession number from Iris."
)
parser.add_argument(
    "-u",
    "--username",
    help="Your Iris username, if different from your current login.",
    required=False,
    default=getpass.getuser(),
)
parser.add_argument("accessionnumber")
args = parser.parse_args()

os.system(
    f"ArcGet.py --host https://iris.mclean.harvard.edu --username {args.username} -l {args.accessionnumber}"
)
