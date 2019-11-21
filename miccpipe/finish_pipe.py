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
from registry import registry_info, DICOMIN, eprint
from run_pipeline_parts import SSH_COMMAND
import receiver_eostudy


def _chown(path, uid, gid):
    os.chown(path, uid, gid)
    for root, dirs, files in os.walk(path):
        for _ in dirs:
            os.chown(pjoin(root, _), uid, gid)
        for _ in files:
            os.chown(pjoin(root, _), uid, gid)


def registry_chown(studydir, reg_info):
    user = reg_info["user"]
    group = reg_info["group"]
    os.rename(pjoin(studydir, ".pipe_complete"), pjoin(studydir, ".pipe_chowned"))
    _chown(studydir, getpwnam(user).pw_uid, getgrnam(group).gr_gid)
    print(f"chowned {studydir} to {user}:{group}")


def sge_job_running(job_id):
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
        return False
    job_id = open(job_id_file).read()
    return sge_job_running(job_id)


def email(studydir, address):
    StudyDateTime = receiver_eostudy.metadata(studydir)["StudyDateTime"]
    subjdir = glob(studydir + "/sub-*")
    subj_msg = ""
    if subjdir:
        subj_msg = "Subject ID used: " + basename(subjdir[0])

    short = studydir.replace(DICOMIN + "/", "")
    msg = EmailMessage()
    msg.set_content(
        f"The MICC Pipeline has finished processing {studydir}.\n"
        f"The acquisition time was {StudyDateTime}.\n"
        + subj_msg
        + "\n\nPlease note that this simply means the pipeline has no more work to do.\n"
        "It does NOT necessarily mean that everything succeeded!\n"
        "You must check your data.\n"
    )
    msg["Subject"] = f"[MICCPIPE] DONE: {short}"
    msg["From"] = "MICC Pipeline <do-not-reply@micc.mclean.harvard.edu>"
    msg["To"] = address
    s = smtplib.SMTP("phsmgout.partners.org")
    s.send_message(msg)
    s.quit()
    print(f"sent completion email for {short} to {address}")


if __name__ == "__main__":
    if os.geteuid() != 0:
        eprint("This program must run as root in order to chown study directories.")
        sys.exit(1)

    for p in Path(DICOMIN).glob("*/" + ".pipe_complete"):
        studydir = str(p.parent)

        fmriprep_jobstatus = fmriprep_running(studydir)

        if fmriprep_jobstatus:
            print(f"not chowning {studydir} yet; fmriprep job incomplete")
            continue
        reg_info = registry_info(studydir)
        registry_chown(studydir, reg_info)
        if "email" in reg_info:
            email(studydir, reg_info["email"])
