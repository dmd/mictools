#!/usr/bin/env python

import glob
import pydicom
from datetime import datetime, timedelta

files = glob.glob("/input/**/*.dcm", recursive=True)

print(files)
