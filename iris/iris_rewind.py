#!/cm/shared/apps/miniforge3/envs/iris/bin/python

import argparse
import os
import sys
from os.path import join as pjoin


def bids_subj_dir(studydir):
    # make sure this is an iris-got directory that has only a single subject
    # in it. we don't want to accidentally rewind a bidsmerged dir
    # check (a) that there is either zero or one directory in the studydir
    # starting with "sub-" and (b) that if there is a "sourcedata" directory
    # that there is ether zero or one directory in it starting with "sub-"
    bids_subj_subdirs = [d for d in os.listdir(studydir) if d.startswith("sub-")]
    sourcedata_subj_subdirs = [
        d for d in os.listdir(pjoin(studydir, "sourcedata")) if d.startswith("sub-")
    ]

    if len(bids_subj_subdirs) != 1:
        print("not exactly one sub- directory found in studydir")
        return False
    if len(sourcedata_subj_subdirs) != 1:
        print("not exactly one sub- directory found in sourcedata")
        return False
    if bids_subj_subdirs != sourcedata_subj_subdirs:
        print("mismatch between sub- directories in studydir and sourcedata")
        return False

    return bids_subj_subdirs[0]


def most_recent_task(studydir):
    tasks = ["bids", "nifti"]
    for task in tasks:
        if os.path.exists(pjoin(studydir, f".taskrun_{task}")):
            return task
    return None


def trash(studydir, files_or_directories):
    trashdir = pjoin(studydir, "DELETE_ME")
    os.makedirs(trashdir, exist_ok=True)
    for file_or_directory in files_or_directories:
        try:
            os.rename(
                pjoin(studydir, file_or_directory), pjoin(trashdir, file_or_directory)
            )
        except Exception as e:
            print(f"Error moving {file_or_directory} to trash: {e}")


def rewind(studydir, task):
    if task == "fmriprep":
        if not directory_state(studydir) == "fmriprep":
            print("studydir is not in fmriprep state")
            sys.exit(1)
        trash(studydir, ["derivatives", ".state-pre-fmriprep", ".jobid"])

    elif task == "bids":
        if not directory_state(studydir) == "bids":
            print("studydir is not in bids state")
            sys.exit(1)

        bids_subj = bids_subj_dir(studydir)
        trash(studydir, [bids_subj])

        # Check if there's a session directory in sourcedata
        sourcedata_subj_dir = pjoin(studydir, "sourcedata", bids_subj)
        contents = os.listdir(sourcedata_subj_dir)

        # If there's a single ses-* directory, move from within it
        session_dirs = [d for d in contents if d.startswith("ses-")]
        if len(session_dirs) == 1:
            session_dir = pjoin(sourcedata_subj_dir, session_dirs[0])
            for d in os.listdir(session_dir):
                os.rename(pjoin(session_dir, d), pjoin(studydir, d))
            os.rmdir(session_dir)
        else:
            # No session or multiple sessions - use original logic
            for d in contents:
                os.rename(pjoin(sourcedata_subj_dir, d), pjoin(studydir, d))

        os.rmdir(sourcedata_subj_dir)
        os.rmdir(pjoin(studydir, "sourcedata"))
        trash(
            studydir,
            [
                ".state-pre-bids",
                "dataset_description.json",
                "README",
                "CHANGES",
                ".bidsignore",
                ".taskrun_bids",
            ],
        )

    elif task == "nifti":
        if not most_recent_task(studydir) == "nifti":
            print("no nifti task found")
            sys.exit(1)
        trash(studydir, [".state-pre-nifti", ".taskrun_nifti", "nifti"])


def directory_state(studydir):
    if (
        os.path.exists(pjoin(studydir, "derivatives"))
        and most_recent_task(studydir) == "bids"
    ):
        return "fmriprep"
    if (
        os.path.exists(pjoin(studydir, "sourcedata"))
        and most_recent_task(studydir) == "bids"
    ):
        return "bids"
    if (
        os.path.exists(pjoin(studydir, "nifti"))
        and most_recent_task(studydir) == "nifti"
    ):
        return "nifti"
    return None


def rewind_to_state(studydir, target_state):
    # Define the states and their order
    states = ["dicom", "nifti", "bids", "fmriprep"]
    current_state = directory_state(studydir)

    if current_state == target_state:
        print("studydir is already in the requested state")
        return

    # Ensure target state is earlier in progression
    current_idx = states.index(current_state)
    target_idx = states.index(target_state)
    if target_idx > current_idx:
        print(f"Cannot rewind from {current_state} to a forward state {target_state}")
        sys.exit(1)

    # Rewind step-by-step
    while current_state != target_state:
        # Determine previous state in progression
        previous_state = states[current_idx - 1]
        rewind(studydir, current_state)

        # Update current state and index
        current_state = previous_state
        current_idx -= 1
        print(f"Rewound to {current_state}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("studydir", help="the study directory to rewind")
    parser.add_argument(
        "rewindto", choices=["dicom", "nifti", "bids"], help="the state to rewind TO"
    )

    args = parser.parse_args()

    # check that studydir is a directory containing at least one .taskrun_<task> file
    if not os.path.isdir(args.studydir):
        print(f"studydir {args.studydir} not found")
        sys.exit(1)
    if not most_recent_task(args.studydir):
        print("no task found - is this a valid studydir?")
        sys.exit(1)

    current_state = directory_state(args.studydir)
    if current_state == args.rewindto:
        print("studydir is already in the requested state")
        sys.exit(0)
    if current_state is None:
        print("studydir is in an unknown state")
        sys.exit(1)

    if current_state and current_state != args.rewindto:
        rewind_to_state(args.studydir, args.rewindto)
        print(f"Studydir is now in {args.rewindto} state")
        print(
            "Please check the studydir to ensure it is in the expected state\n"
            "and remove the DELETE_ME directory if everything looks good."
        )
