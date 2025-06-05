#!/cm/shared/apps/miniforge3/envs/iris/bin/python

import argparse
import getpass
import os
import requests
import sys
import tabulate
import xml.etree.ElementTree as ET
from operator import itemgetter


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
parser.add_argument("-v", action="store_true", help=argparse.SUPPRESS)
parser.add_argument(
    "--noauthfile",
    help="Do not use .xnat_auth file for login even if present.",
    required=False,
    action="store_true",
)
args = parser.parse_args()


def read_auth_file():
    """Read credentials from ~/.xnat_auth XML file."""
    auth_file = os.path.expanduser("~/.xnat_auth")
    try:
        tree = ET.parse(auth_file)
        root = tree.getroot()
        iris_node = root.find(".//iris[@version='1.5']")
        if iris_node is not None:
            username = iris_node.find("username")
            password = iris_node.find("password")
            if username is not None and password is not None:
                return username.text, password.text
    except (ET.ParseError, FileNotFoundError):
        pass
    return None, None


# Check if we should use authfile
password = None
if (
    os.path.exists(os.path.expanduser("~/.xnat_auth"))
    and not args.noauthfile
    and args.username == getpass.getuser()
):
    print("Using .xnat_auth file for login. Use --noauthfile to override.")
    auth_username, password = read_auth_file()
    if auth_username and password:
        args.username = auth_username
    else:
        print("Failed to read credentials from .xnat_auth file.")

if not password:
    password = getpass.getpass(f"Iris password for {args.username}: ")

r = requests.get(
    "https://iris.mclean.harvard.edu/data/search/saved/xs1620078537830/results?format=json",
    auth=(args.username, password),
)

if not r.ok:
    print("Something went wrong.")
    if args.v:
        print(r.text)
    sys.exit(1)

sessions = sorted(
    r.json()["ResultSet"]["Result"], key=itemgetter("date"), reverse=True
)[: args.n]

fields = ["date", "project", "label", "xnat_subjectdata_subject_label"]

print(tabulate.tabulate(map(itemgetter(*fields), sessions), tablefmt="plain"))
