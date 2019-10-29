#!/usr/bin/env python

import os
from pathlib import Path
from pwd import getpwnam
from grp import getgrnam
from os.path import join as pjoin
import subprocess
import smtplib
from email.message import EmailMessage
from registry import registry_info, DICOMIN


def _chown(path, uid, gid):
    os.chown(path, uid, gid)
    for root, dirs, files in os.walk(path):
        for _ in dirs:
            os.chown(os.path.join(root, _), uid, gid)
        for _ in files:
            os.chown(os.path.join(root, _), uid, gid)


def registry_chown(studydir, reg_info):
    user = reg_info["user"]
    group = reg_info["group"]

    print(f"chown {studydir} to {user}:{group}")
    os.rename(pjoin(studydir, ".pipe_complete"), pjoin(studydir, ".pipe_chowned"))
    _chown(studydir, getpwnam(user).pw_uid, getgrnam(group).gr_gid)


def sge_job_running(job_id):
    qstat = (
        subprocess.check_output(
            ["/cm/shared/apps/sge/2011.11p1/bin/linux-x64/qstat", "-u", "*"],
            env={"SGE_ROOT": "/cm/shared/apps/sge/current"},
        )
        .decode()
        .split("\n")
    )
    qline = [_ for _ in qstat if _.startswith(" " + job_id)]
    if not qline:
        return False
    job_status = qline[0].split()[4]
    return job_status in ("r", "qw", "hqw")


def email(studydir, address):
    msg = EmailMessage()
    msg.set_content(
        f"The MICC Pipeline has finished processing {studydir}."
        "\n\nPlease note that this simply means the pipeline has no more work to do;"
        "it does NOT necessarily mean that everything succeeded! You must check your data."
    )
    msg["Subject"] = f"[MICCPIPE] DONE: {studydir}"
    msg["From"] = "Do Not Reply <do-not-reply@micc.mclean.harvard.edu>"
    msg["To"] = address
    s = smtplib.SMTP("phsmgout.partners.org")
    s.send_message(msg)
    s.quit()


def fmriprep_running(studydir):
    job_id_file = pjoin(studydir, ".pipe_sgejobid")
    if not os.path.exists(job_id_file):
        return False
    job_id = open(job_id_file).read()
    return sge_job_running(job_id)


if __name__ == "__main__":
    for p in Path(DICOMIN).glob("*/" + ".pipe_complete"):
        studydir = str(p.parent)
        if fmriprep_running(studydir):
            print(f"not chowning {studydir}; fmriprep job incomplete")
            continue
        reg_info = registry_info(studydir)
        if "email" in reg_info:
            email(studydir, reg_info["email"])
        registry_chown(studydir, reg_info)
