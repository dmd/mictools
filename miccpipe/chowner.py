#!/usr/bin/env python

import os
from pathlib import Path
from pwd import getpwnam
from grp import getgrnam
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
    _chown(studydir, getpwnam(user).pw_uid, getgrnam(group).gr_gid)


if __name__ == "__main__":
    for p in Path(DICOMIN).glob("*/" + ".pipecomplete"):
        studydir = str(p.parent)
        reg_info = registry_info(studydir)
        registry_chown(studydir, reg_info)
