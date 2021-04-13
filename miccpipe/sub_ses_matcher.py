import csv
import logging
import random
import requests
import smtplib

from os.path import join as pjoin
from email.message import EmailMessage
from io import StringIO

from registry import registry_info, task_select, DICOMIN
from receiver_eostudy import metadata

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)

SHEET = "http://micc.mclean.harvard.edu:11051/?AccessionNumber="
SHEETFILE = pjoin(DICOMIN, "registry", "accession.csv")


def sheet_lookup(AccessionNumber):
    mapping = {}
    for row in csv.reader(open(SHEETFILE)):
        mapping[row[0]] = row[1], row[2]

    if AccessionNumber in mapping:
        logging.info(f"Found {mapping[AccessionNumber]} for {AccessionNumber}")
        return mapping[AccessionNumber]
    else:
        logging.warning(f"Did not find {AccessionNumber} in sheet.")
        return (None, None)


def send_form_email(studydir):
    # send email asking the user to fill out the form so we know what sub/ses
    # to assign

    reg_info = registry_info(studydir)
    tasks = task_select(reg_info["run"])
    if not tasks["bids"]:
        logging.info("Not doing BIDS, so not sending email.")
        return

    if tasks["bids"] and "email" not in reg_info:
        logging.warning(
            "Error: I need to send email, but there isn't one in the registry."
        )
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
    logging.info(f"Sent form request email for {AccessionNumber} to {address}")
    open(pjoin(studydir, ".pipe_emailsent"), "a").write("")
