#!/cm/shared/anaconda3/envs/iris/bin/python

import sys
import requests
from operator import itemgetter
import getpass
import argparse
import tabulate


parser = argparse.ArgumentParser(description="List your latest studies from Iris.")
parser.add_argument(
    "-u",
    "--username",
    help="Your Iris username, if different from your current login.",
    required=False,
    default=getpass.getuser(),
)
parser.add_argument(
    "-n",
    help="How many recent to retrieve. (Default: 10)",
    default=10,
    required=False,
    type=int,
)
args = parser.parse_args()

password = getpass.getpass("Enter XNAT passphrase: ")

r = requests.get(
    "https://iris.mclean.harvard.edu/data/search/saved/xs1617721281007/results?format=json",
    auth=(args.username, password),
)

if not r.ok:
    print("Something went wrong.")
    sys.exit(1)

sessions = sorted(
    r.json()["ResultSet"]["Result"], key=itemgetter("date"), reverse=True
)[: args.n]

fields = ["date", "project", "label", "xnat_subjectdata_subject_label"]

print(tabulate.tabulate(map(itemgetter(*fields), sessions), tablefmt="plain"))
