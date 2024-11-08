import os
from pathlib import Path
import shutil
from iris_rewind import *

testdir_source = "tests/iris/rewind"


def create_testdir(testname):
    testdir = f"tests/iris/rewind_test_{testname}"
    shutil.copytree(testdir_source, testdir)
    return testdir


def destroy_testdir(testname):
    testdir = f"tests/iris/rewind_test_{testname}"
    shutil.rmtree(testdir)


def test_bids_subj_dir():
    testdir = create_testdir("bids_subj_dir")

    # Test case: valid BIDS subject directory
    assert bids_subj_dir(testdir) == "sub-1"

    # Test case: no BIDS subject directory
    shutil.rmtree(f"{testdir}/sourcedata/sub-1")
    assert not bids_subj_dir(testdir)

    # Test case: multiple BIDS subject directories
    os.makedirs(f"{testdir}/sourcedata/sub-1")
    os.makedirs(f"{testdir}/sourcedata/sub-2")
    assert not bids_subj_dir(testdir)

    # Test case: invalid BIDS subject directory
    shutil.rmtree(f"{testdir}/sourcedata/sub-1")
    shutil.rmtree(f"{testdir}/sourcedata/sub-2")
    os.makedirs(f"{testdir}/sourcedata/invalid-sub")
    assert not bids_subj_dir(testdir)

    destroy_testdir("bids_subj_dir")


def test_rewind_fmriprep():
    testdir = create_testdir("rewind_fmriprep")

    rewind(testdir, "fmriprep")
    assert not os.path.exists(f"{testdir}/derivatives")
    assert not os.path.exists(f"{testdir}/.state-pre-fmriprep")
    assert not os.path.exists(f"{testdir}/.jobid")

    destroy_testdir("rewind_fmriprep")


def test_rewind_bids():
    testdir = create_testdir("rewind_bids")

    rewind(testdir, "fmriprep")
    rewind(testdir, "bids")
    assert not os.path.exists(f"{testdir}/sourcedata/sub-1")
    assert not os.path.exists(f"{testdir}/sourcedata")
    assert not os.path.exists(f"{testdir}/.state-pre-bids")
    assert not os.path.exists(f"{testdir}/dataset_description.json")
    assert not os.path.exists(f"{testdir}/README")
    assert not os.path.exists(f"{testdir}/CHANGES")
    assert not os.path.exists(f"{testdir}/.bidsignore")
    assert not os.path.exists(f"{testdir}/.taskrun_bids")

    assert os.path.exists(f"{testdir}/nifti/restingstate_10.json")
    assert os.path.exists(f"{testdir}/scans/10-restingstate")
    assert os.path.exists(f"{testdir}/.state-pre-nifti")

    destroy_testdir("rewind_bids")


def test_rewind_nifti():
    testdir = create_testdir("rewind_nifti")

    rewind(testdir, "fmriprep")
    rewind(testdir, "bids")
    rewind(testdir, "nifti")
    assert not os.path.exists(f"{testdir}/.state-pre-nifti")
    assert not os.path.exists(f"{testdir}/.taskrun_nifti")
    assert not os.path.exists(f"{testdir}/nifti")

    destroy_testdir("rewind_nifti")


def test_directory_state():
    testdir = create_testdir("directory_state")

    assert directory_state(testdir) == "fmriprep"
    rewind(testdir, "fmriprep")
    assert directory_state(testdir) == "bids"
    assert not directory_state(testdir) == "fmriprep"

    rewind(testdir, "bids")
    assert directory_state(testdir) == "nifti"
    assert not directory_state(testdir) == "bids"

    rewind(testdir, "nifti")
    assert directory_state(testdir) == None
    assert not directory_state(testdir) == "nifti"

    destroy_testdir("directory_state")


def test_rewind_to_state():
    testdir = create_testdir("rewind_to_state")

    rewind_to_state(testdir, "dicom")
    assert not os.path.exists(f"{testdir}/.state-pre-nifti")
    assert not os.path.exists(f"{testdir}/.taskrun_nifti")
    assert not os.path.exists(f"{testdir}/nifti")

    destroy_testdir("rewind_to_state")
