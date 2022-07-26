#!/usr/bin/env python

import os

def missing_elements(L):
    start, end = L[0], L[-1]
    return sorted(set(range(start, end + 1)).difference(L))

# Prismas add some stuff with scan# 99 and up, but we don't care.
NOT_OVER = 99
missing = ', '.join([str(x) for x in missing_elements(sorted([int(x) for x in os.listdir('/input/SCANS') if int(x) < NOT_OVER]))])

if missing:
    print(f"Session has gaps: {missing}")
