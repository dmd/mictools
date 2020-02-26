#!/usr/bin/env python3

import yaml
import os.path
from os.path import join as pjoin
import sys
import re
from registry import DICOMIN, condensed_name


if __name__ == "__main__":
    regfile = pjoin(DICOMIN, "registry", sys.argv[1]) + ".yaml"
    if os.path.exists(sys.argv[1]):
        filename = sys.argv[1]
    elif os.path.exists(regfile):
        filename = regfile
    else:
        print(f"Could not open file {regfile} or {os.path.abspath(sys.argv[1])}.")
        sys.exit(1)

    print(f"Trying to read {os.path.abspath(filename)}...")

    rawregistry = {}
    registry = {}
    try:
        rawregistry.update(yaml.safe_load(open(filename)))
    except:
        print(f"Could not parse it at all; giving up. Your file is NOT OK.")
        sys.exit(1)

    for k in rawregistry:
        registry[condensed_name(k)] = rawregistry[k]

    print(
        """
    The system parsed your file as follows. Does it look OK to you?
    Please note:
       * Order does not matter; only the indent structure matters.
       * The study description is simplified to all-caps alphanumeric.
       """
    )
    print(yaml.dump(registry, indent=4))
