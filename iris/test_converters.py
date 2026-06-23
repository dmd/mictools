import os
from converters import final_scan, convert_to_bids, convert_to_nifti
import yaml
import importlib
from pathlib import Path
import shutil

irisfmriprep = importlib.import_module("iris-fmriprep")
testdir = "tests/iris/convert_to_bids"
testdir_orig = testdir + ".orig"


def test_final_scan():
    assert final_scan(["foo_11.nii.gz", "foo_2.nii.gz", "foo_3.nii.gz"], False) == [
        "foo_11.nii.gz"
    ]

    assert final_scan(
        ["foo_11.nii.gz", "foo_1013.nii.gz", "foo_2.nii.gz", "foo_3.nii.gz"], False
    ) == ["foo_11.nii.gz"]

    assert final_scan(
        [
            "foo_37_e1.nii.gz",
            "foo_37_e2.nii.gz",
            "foo_38_e1.nii.gz",
            "foo_38_e2.nii.gz",
        ],
        True,
    ) == [
        "foo_38_e1.nii.gz",
        "foo_38_e2.nii.gz",
    ]


def test_convert_to_bids():
    shutil.copytree(testdir, testdir_orig, copy_function=os.link)

    convert_to_nifti(f"{testdir}/phantom-20220812")

    should_exist_nifti = [
        "T1w_MEMPRAGE_RMS_7.nii.gz",
        "T1w_MEMPRAGE_RMS_9.nii.gz",
        "T1w_MEMPRAGE_RMS_11.nii.gz",
        "T1w_MEMPRAGE_10_e2.nii.gz",  # ensure updated dcm2niix that names echoes correctly
        "rfMRI_REST_SINGLEECHO_AP_35.nii.gz",
        "rfMRI_REST_SINGLEECHO_AP_37.nii.gz",
        "rfMRI_REST_SINGLEECHO_AP_39.nii.gz",
        "rfMRI_REST_SINGLEECHO_PA_33.nii.gz",
        "rfMRI_REST_MULTIECHO_AP_19_e4.nii.gz",
        "rfMRI_REST_MULTIECHO_PA_21_e4.nii.gz",
    ]

    should_exist_bids = [
        "CHANGES",
        "README",
        ".bidsignore",
        "dataset_description.json",
        "sub-test/ses-1/anat/sub-test_ses-1_T1w.json",
        "sub-test/ses-1/anat/sub-test_ses-1_T1w.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-rest_acq-singleecho_dir-AP_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-rest_acq-singleecho_dir-AP_bold.json",
        "sub-test/ses-1/func/sub-test_ses-1_task-rest_acq-singleecho_dir-PA_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-rest_acq-singleecho_dir-PA_bold.json",
        "sub-test/ses-1/func/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-1_echo-1_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-1_echo-2_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-1_echo-3_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-1_echo-4_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-rest_acq-multiecho_dir-PA_run-1_echo-1_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-rest_acq-multiecho_dir-PA_run-1_echo-2_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-rest_acq-multiecho_dir-PA_run-1_echo-3_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-rest_acq-multiecho_dir-PA_run-1_echo-4_bold.nii.gz",
    ]

    for f in should_exist_nifti:
        assert Path(f"{testdir}/phantom-20220812/nifti/{f}").exists()

    config = yaml.safe_load(open(f"{testdir}/phantom-20220812.yaml"))
    convert_to_bids(config, f"{testdir}/phantom-20220812", "test", "1")

    for f in should_exist_bids:
        assert Path(f"{testdir}/phantom-20220812/{f}").exists()

    # clean up
    shutil.rmtree(testdir)
    shutil.move(testdir_orig, testdir)


def test_convert_to_bids_keep_all_runs():
    # keep_all_runs preserves every repeated acquisition with run-XX tags and
    # pairs each BOLD run with its preceding SBRef companion (suffix _sbref),
    # instead of keeping only the last run.
    shutil.copytree(testdir, testdir_orig, copy_function=os.link)
    try:
        convert_to_nifti(f"{testdir}/phantom-20220812")

        config = yaml.safe_load(open(f"{testdir}/phantom-20220812.yaml"))
        convert_to_bids(
            config, f"{testdir}/phantom-20220812", "test", "1", keep_all_runs=True
        )

        anat = "sub-test/ses-1/anat"
        func = "sub-test/ses-1/func"
        should_exist_bids = [
            # repeated anat runs are kept and tagged run-01..run-03
            f"{anat}/sub-test_ses-1_run-01_T1w.nii.gz",
            f"{anat}/sub-test_ses-1_run-01_T1w.json",
            f"{anat}/sub-test_ses-1_run-02_T1w.nii.gz",
            f"{anat}/sub-test_ses-1_run-03_T1w.nii.gz",
            # single-echo AP: 3 repeats, each BOLD paired with its SBRef
            f"{func}/sub-test_ses-1_task-rest_acq-singleecho_dir-AP_run-01_bold.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-singleecho_dir-AP_run-01_bold.json",
            f"{func}/sub-test_ses-1_task-rest_acq-singleecho_dir-AP_run-01_sbref.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-singleecho_dir-AP_run-02_bold.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-singleecho_dir-AP_run-02_sbref.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-singleecho_dir-AP_run-03_bold.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-singleecho_dir-AP_run-03_sbref.nii.gz",
            # single-echo PA: only one run, so no run tag, but SBRef is still kept
            f"{func}/sub-test_ses-1_task-rest_acq-singleecho_dir-PA_bold.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-singleecho_dir-PA_sbref.nii.gz",
            # multi-echo AP: config name has run-1, reconciled to run-01..run-03
            # (not duplicated to run-1_run-01); all 4 echoes for BOLD and SBRef
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-01_echo-1_bold.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-01_echo-1_bold.json",
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-01_echo-1_sbref.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-01_echo-4_bold.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-02_echo-1_bold.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-02_echo-1_sbref.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-03_echo-1_bold.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-03_echo-4_bold.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-03_echo-4_sbref.nii.gz",
            # multi-echo PA: only one run, so config run-1 is kept; SBRef kept too
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-PA_run-1_echo-1_bold.nii.gz",
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-PA_run-1_echo-1_sbref.nii.gz",
        ]

        should_not_exist_bids = [
            # the run entity must not be duplicated (config run-1 + new run-01)
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-1_run-01_echo-1_bold.nii.gz",
            # with repeats kept and tagged, the untagged name must not appear
            f"{func}/sub-test_ses-1_task-rest_acq-singleecho_dir-AP_bold.nii.gz",
            # only three AP runs exist
            f"{func}/sub-test_ses-1_task-rest_acq-multiecho_dir-AP_run-04_echo-1_bold.nii.gz",
        ]

        for f in should_exist_bids:
            assert Path(f"{testdir}/phantom-20220812/{f}").exists(), f

        for f in should_not_exist_bids:
            assert not Path(f"{testdir}/phantom-20220812/{f}").exists(), f
    finally:
        # clean up
        shutil.rmtree(testdir)
        shutil.move(testdir_orig, testdir)
