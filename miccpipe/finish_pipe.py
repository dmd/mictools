#!/usr/bin/env python

import os
import sys
from pathlib import Path
from pwd import getpwnam
from grp import getgrnam
from os.path import basename, join as pjoin
from glob import glob
import subprocess
import smtplib
import requests
from email.message import EmailMessage
from registry import registry_info, DICOMIN
from run_pipeline_parts import SSH_COMMAND
import receiver_eostudy
import logging

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)


def _chown(path, uid, gid):
    if os.path.exists(path):
        os.chown(path, uid, gid)
        os.chmod(path, 0o770)
        for root, dirs, files in os.walk(path):
            for _ in dirs:
                os.chown(pjoin(root, _), uid, gid)
                os.chmod(pjoin(root, _), 0o770)
            for _ in files:
                os.chown(pjoin(root, _), uid, gid)
                os.chmod(pjoin(root, _), 0o660)


def registry_chown(studydir, reg_info):
    user = reg_info["user"]
    group = reg_info["group"]
    for p in studydir, pjoin(DICOMIN, "fmriprep-working", basename(studydir)):
        _chown(p, getpwnam(user).pw_uid, getgrnam(group).gr_gid)
        logging.info(f"chowned {p} to {user}:{group}")
    os.rename(pjoin(studydir, ".pipe_complete"), pjoin(studydir, ".pipe_chowned"))


def fmriprep_job_errorfree(job_id):
    errorfree = False

    # two possible places this can be.  we will set to True
    # if we can find the text in one of the two places.

    # it can be in the error file, with one phrasing
    e_file = glob("/home/pipeline/*e" + job_id)
    e_text = "fMRIPrep finished without errors"

    # or it can be in the output file, with a different phrasing
    o_file = glob("/home/pipeline/*o" + job_id)
    o_text = "fMRIPrep finished successfully"

    if len(e_file) != 1:
        logging.warning(f"Could not find job error output for jobid {job_id}")
    else:
        e_file = e_file[0]

        try:
            with open(e_file) as f:
                if e_text in f.read():
                    errorfree = True
        except:
            logging.info(
                f"something went wrong trying to look in the error file {e_file}"
            )

    if len(o_file) != 1:
        logging.warning(f"Could not find job output for jobid {job_id}")
    else:
        o_file = o_file[0]

        try:
            with open(o_file) as f:
                if o_text in f.read():
                    errorfree = True
        except:
            logging.warning(
                f"something went wrong trying to look in the output file {o_file}"
            )

    return errorfree


def sge_job_running(job_id):
    logging.info(f"checking sge_job_running for {job_id}")
    cmd = ["/cm/shared/apps/sge/2011.11p1/bin/linux-x64/qstat", "-u", '"*"']
    if os.environ.get("INSIDE_DOCKER", False) == "yes":
        cmd = SSH_COMMAND + cmd
    qstat = (
        subprocess.check_output(cmd, env={"SGE_ROOT": "/cm/shared/apps/sge/current"})
        .decode()
        .split("\n")
    )
    qline = [_ for _ in qstat if _.startswith(" " + job_id)]
    if not qline:
        return False
    job_status = qline[0].split()[4]
    return job_status in ("r", "qw", "hqw")


def fmriprep_running(studydir):
    job_id_file = pjoin(studydir, ".pipe_sgejobid")
    if not os.path.exists(job_id_file):
        logging.warning(f"job_id_file {job_id_file} not found")
        return False, False
    job_id = open(job_id_file).read()
    return sge_job_running(job_id), fmriprep_job_errorfree(job_id)


def email(studydir, address, fmriprep_was_errorfree):
    StudyDateTime = receiver_eostudy.metadata(studydir)["StudyDateTime"]
    subjdir = glob(studydir + "/sub-*")
    subj_msg = ""
    if subjdir:
        subj_msg = "Subject ID used: " + basename(subjdir[0])

    if fmriprep_was_errorfree:
        fwe = "fMRIPrep claimed to complete without errors.\n"
    else:
        fwe = "It looks like fMRIPrep did NOT complete successfully. Check the logs for details.\n"

    short = studydir.replace(DICOMIN + "/", "")
    msg = EmailMessage()
    msg.set_content(
        f"The MICC Pipeline has finished processing {studydir}\n"
        f"The acquisition time was {StudyDateTime}.\n"
        + subj_msg
        + "\n\nPlease note that this simply means the pipeline has no more work to do.\n"
        "It does NOT necessarily mean that everything succeeded!\n"
        + fwe
        + "No matter what, it is up to you to check your data.\n\n"
        "You MUST move your data out of " + DICOMIN + " to your own data area.\n"
        "Data left in "
        + DICOMIN
        + " is not backed up, and will be removed after 30 days.\n"
    )
    msg["Subject"] = f"[MICCPIPE] DONE: {short}"
    msg["From"] = "MICC Pipeline <do-not-reply@micc.mclean.harvard.edu>"
    msg["To"] = address
    s = smtplib.SMTP("phsmgout.partners.org")
    s.send_message(msg)
    s.quit()
    logging.info(f"sent completion email for {short} to {address}")


if __name__ == "__main__":
    if os.geteuid() != 0:
        logging.critical(
            "This program must run as root in order to chown study directories."
        )
        sys.exit(1)

    logging.info("running finisher")
    check = False
    for p in Path(DICOMIN).glob("*/" + ".pipe_complete"):
        check = True
        studydir = str(p.parent)

        logging.info(f"checking fmriprep_running for {studydir}")
        fmriprep_is_running, fmriprep_was_errorfree = fmriprep_running(studydir)

        if fmriprep_is_running:
            logging.info(f"not chowning {studydir} yet; fmriprep job incomplete")
            continue
        reg_info = registry_info(studydir)
        logging.info(f"chowning {studydir}")
        registry_chown(studydir, reg_info)
        if "email" in reg_info:
            email(studydir, reg_info["email"], fmriprep_was_errorfree)
    if not check:
        logging.info("no work to do - no .pipe_complete files found")
