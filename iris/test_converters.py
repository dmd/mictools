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
