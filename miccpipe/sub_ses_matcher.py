import requests
import smtplib
from io import StringIO
import random
from os.path import join as pjoin
import csv
from email.message import EmailMessage
from registry import registry_info, task_select, DICOMIN
from receiver_eostudy import metadata

SHEET = "http://micc.mclean.harvard.edu:11051/?AccessionNumber="
SHEETFILE = pjoin(DICOMIN, "registry", "accession.csv")


def sheet_lookup(AccessionNumber):
    mapping = {}
    for row in csv.reader(open(SHEETFILE)):
        mapping[row[0]] = row[1], row[2]

    if AccessionNumber in mapping:
        print(f"Found {mapping[AccessionNumber]} for {AccessionNumber}")
        return mapping[AccessionNumber]
    else:
        print(f"Did not find {AccessionNumber} in sheet.")
        return (None, None)


def send_form_email(studydir):
    # send email asking the user to fill out the form so we know what sub/ses
    # to assign

    reg_info = registry_info(studydir)
    tasks = task_select(reg_info["run"])
    if not tasks["bids"]:
        print("Not doing BIDS, so not sending email.")
        return

    if tasks["bids"] and "email" not in reg_info:
        print("Error: I need to send email, but there isn't one in the registry.")
        return

    address = reg_info["email"]
    AccessionNumber = metadata(studydir)["AccessionNumber"]
    msg = EmailMessage()
    msg.set_content(
        """\
    The MICC Pipeline has received your study. In order to continue,
    it needs the subject and optionally the session id you wish to use.
    Please fill out this form:

    """
        + SHEET
        + AccessionNumber
        + """

    Thank you,
    The MICC Pipeline"""
    )

    msg["Subject"] = f"[MICCPIPE] Need sub/ses info for {AccessionNumber}"
    msg["From"] = "MICC Pipeline <do-not-reply@micc.mclean.harvard.edu>"
    msg["To"] = address
    s = smtplib.SMTP("phsmgout.partners.org")
    s.send_message(msg)
    s.quit()
    print(f"Sent form request email for {AccessionNumber} to {address}")
    open(pjoin(studydir, ".pipe_emailsent"), "a").write("")
