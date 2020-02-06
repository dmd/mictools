#!/usr/bin/env python3

import os
import time
from pathlib import Path
from registry import DICOMIN, EOSTUDY_TIMEOUT
from receiver_eostudy import prepare_study

while True:
    now = time.time()

    dirs = [
        f.path
        for f in os.scandir(DICOMIN)
        if f.is_dir()
        and os.path.basename(f).startswith("PIPE")
        and not os.path.exists(Path(f) / ".STUDY_METADATA")
        and (now - os.stat(f).st_mtime) > EOSTUDY_TIMEOUT
    ]

    for d in dirs:
        prepare_study(d)

    time.sleep(15)
