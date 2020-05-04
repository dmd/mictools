#!/usr/bin/env python3

import os
import time
from pathlib import Path
from registry import DICOMIN, EOSTUDY_TIMEOUT
from receiver_eostudy import prepare_study

while True:
    now = time.time()

    # process directories that are:
    # - PIPE*, so written by storescp
    # - not already handled by prepare_study
    # - not still being written to in the last EOSTUDY_TIMEOUT seconds
    # - written in the last day
    # There is probably a race condition here if multiple copies of this
    # were run in parallel.

    dirs = [
        f.path
        for f in os.scandir(DICOMIN)
        if f.is_dir()
        and os.path.basename(f).startswith("PIPE")
        and not os.path.exists(Path(f) / ".STUDY_METADATA")
        and (now - os.stat(f).st_mtime) > EOSTUDY_TIMEOUT
        and (now - os.stat(f).st_mtime) < 86400
    ]

    for d in dirs:
        try:
            prepare_study(d)
        except IndexError:
            # IndexError is raised if there are no MR* files
            print(f"No MR* files in studydir {d}")
            pass

    time.sleep(15)
