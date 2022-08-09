from converters import final_scan, convert_to_bids, convert_to_nifti
import yaml
import importlib
from pathlib import Path
import shutil

irisfmriprep = importlib.import_module("iris-fmriprep")
testdir = "tests/iris/convert_to_bids"
testdir_orig = testdir + ".orig"


def test_final_scan():
    assert final_scan(
        ["FOO_BAR_11.nii.gz", "FOO_BAR_2.nii.gz", "FOO_BAR_3.nii.gz"], False
    ) == ["FOO_BAR_11.nii.gz"]

    assert final_scan(
        [
            "checkerboard_AP_SBRef_37_e1.nii.gz",
            "checkerboard_AP_SBRef_37_e2.nii.gz",
            "checkerboard_AP_SBRef_37_e3.nii.gz",
            "checkerboard_AP_SBRef_38_e1.nii.gz",
            "checkerboard_AP_SBRef_38_e2.nii.gz",
            "checkerboard_AP_SBRef_38_e3.nii.gz",
        ],
        True,
    ) == [
        "checkerboard_AP_SBRef_38_e1.nii.gz",
        "checkerboard_AP_SBRef_38_e2.nii.gz",
        "checkerboard_AP_SBRef_38_e3.nii.gz",
    ]


def test_convert_to_bids():
    shutil.copytree(testdir, testdir_orig)

    convert_to_nifti(f"{testdir}/EXAMPLE")

    should_exist_nifti = [
        "T1_MEMPRAGE_64ch_6_e1.json",
        "T1_MEMPRAGE_64ch_6_e1.nii.gz",
        "T1_MEMPRAGE_64ch_6_e2.json",
        "T1_MEMPRAGE_64ch_6_e2.nii.gz",
        "T1_MEMPRAGE_64ch_6_e3.json",
        "T1_MEMPRAGE_64ch_6_e3.nii.gz",
        "T1_MEMPRAGE_64ch_6_e4.json",
        "T1_MEMPRAGE_64ch_6_e4.nii.gz",
        "T1_MEMPRAGE_64ch_RMS_7.json",
        "T1_MEMPRAGE_64ch_RMS_7.nii.gz",
        "restingstate_10.json",
        "restingstate_10.nii.gz",
        "restingstate_11_ph.json",
        "restingstate_11_ph.nii.gz",
        "checkerboard_AP_SBRef_37_e1.json",
        "checkerboard_AP_SBRef_37_e1.nii.gz",
        "checkerboard_AP_SBRef_37_e2.json",
        "checkerboard_AP_SBRef_37_e2.nii.gz",
        "checkerboard_AP_SBRef_37_e3.json",
        "checkerboard_AP_SBRef_37_e3.nii.gz",
        "checkerboard_AP_SBRef_38_e1.json",
        "checkerboard_AP_SBRef_38_e1.nii.gz",
        "checkerboard_AP_SBRef_38_e2.json",
        "checkerboard_AP_SBRef_38_e2.nii.gz",
        "checkerboard_AP_SBRef_38_e3.json",
        "checkerboard_AP_SBRef_38_e3.nii.gz",
    ]

    should_exist_bids = [
        "CHANGES",
        "README",
        ".bidsignore",
        "dataset_description.json",
        "sub-test/ses-1/anat/sub-test_ses-1_T1w.json",
        "sub-test/ses-1/anat/sub-test_ses-1_T1w.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-resting_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-resting_bold.json",
        "sub-test/ses-1/func/sub-test_ses-1_task-checkerboard_dir-AP_echo-1_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-checkerboard_dir-AP_echo-1_bold.json",
        "sub-test/ses-1/func/sub-test_ses-1_task-checkerboard_dir-AP_echo-2_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-checkerboard_dir-AP_echo-2_bold.json",
        "sub-test/ses-1/func/sub-test_ses-1_task-checkerboard_dir-AP_echo-3_bold.nii.gz",
        "sub-test/ses-1/func/sub-test_ses-1_task-checkerboard_dir-AP_echo-3_bold.json",
    ]

    for f in should_exist_nifti:
        assert Path(f"{testdir}/EXAMPLE/nifti/{f}").exists()

    config = yaml.safe_load(open(f"{testdir}/EXAMPLE.yaml"))
    convert_to_bids(config, f"{testdir}/EXAMPLE", "test", "1")

    for f in should_exist_bids:
        assert Path(f"{testdir}/EXAMPLE/{f}").exists()

    # clean up
    shutil.rmtree(testdir)
    shutil.move(testdir_orig, testdir)
