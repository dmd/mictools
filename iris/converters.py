from glob import glob
import shutil
import logging
import os
from os.path import join as pjoin
from nipype.interfaces.dcm2nii import Dcm2niix
import re
from preprocess import preprocess

niigz = ".nii.gz"

# make sure we use system dcm2niix
os.environ["PATH"] = "/usr/local/bin:" + os.environ["PATH"]


def final_scan(sourcenames, multiecho=False):
    # if single-echo:
    #  given ['FOO_BAR_11.nii.gz', 'FOO_BAR_2.nii.gz', 'FOO_BAR_1234.nii.gz', 'FOO_BAR_3.nii.gz']
    #  return 'FOO_BAR_11.nii.gz', the highest numbered scan < 1000
    # if multi-echo
    #  given:
    #   ['checkerboard_AP_SBRef_37_e1.nii.gz',
    #   'checkerboard_AP_SBRef_37_e2.nii.gz',
    #   'checkerboard_AP_SBRef_37_e3.nii.gz',
    #   'checkerboard_AP_SBRef_38_e1.nii.gz',
    #   'checkerboard_AP_SBRef_38_e2.nii.gz',
    #   'checkerboard_AP_SBRef_38_e3.nii.gz']
    #
    #  return:
    #   ['checkerboard_AP_SBRef_38_e1.nii.gz',
    #   'checkerboard_AP_SBRef_38_e2.nii.gz',
    #   'checkerboard_AP_SBRef_38_e3.nii.gz']

    if not sourcenames:
        return []

    files = {}
    for file in sourcenames:

        if multiecho:
            m = re.search(rf"_(\d+)_e\d{niigz}$", file)
        else:
            m = re.search(rf"_(\d+){niigz}$", file)

        fid = int(m.group(1))

        if fid >= 1000:
            continue  # ignore files with numbers >= 1000

        if fid not in files:
            files[fid] = []
        files[fid].append(file)

    ids = sorted(list(files.keys()))

    return sorted(files[ids[-1]])


def record_studydir_state(studydir, task):
    # record the state of the studydir before we start messing with it
    state_file = pjoin(studydir, f".state-pre-{task}")
    with open(state_file, "w") as f:
        for root, dirs, files in os.walk(studydir):
            for name in sorted(dirs + files):
                relpath = os.path.relpath(pjoin(root, name), studydir)
                if relpath != os.path.relpath(state_file, studydir):
                    f.write(relpath + "\n")


def convert_to_nifti(studydir):
    logging.info("Converting to nifti")
    dicomdir = pjoin(studydir, "scans")
    niftidir = pjoin(studydir, "nifti")
    os.mkdir(niftidir)
    dcm = Dcm2niix()
    dcm.ignore_exception = True
    dcm.inputs.source_dir = dicomdir
    dcm.inputs.output_dir = niftidir
    dcm.inputs.out_filename = "%d_%s"
    dcm.run()


def convert_to_bids(config, studydir, subject, session, keep_all_runs=False):
    logging.info("Organizing in BIDS format")
    EXTENSIONS = (".json", ".bval", ".bvec", ".tsv", niigz)
    sourcedata_dir = pjoin(studydir, "sourcedata", "sub-" + subject)
    subject_dir = pjoin(studydir, "sub-" + subject)

    if session:
        sourcedata_dir = pjoin(sourcedata_dir, "ses-" + session)
        subject_dir = pjoin(subject_dir, "ses-" + session)

    os.makedirs(sourcedata_dir, exist_ok=True)
    os.makedirs(subject_dir, exist_ok=True)

    open(pjoin(studydir, "dataset_description.json"), "w").write(
        """
        {
            "Name": "Investigator Name",
            "BIDSVersion": "1.10.0",
            "Authors": ["name1", "name1"],
            "Funding": ["Funding Agency"]
        }
        """
    )
    open(pjoin(studydir, "README"), "w").write("\n")
    open(pjoin(studydir, "CHANGES"), "w").write("\n")
    bids_ignore = [".job*", ".task*", ".state*"]
    with open(pjoin(studydir, ".bidsignore"), "w") as f:
        f.write("\n".join(bids_ignore) + "\n")

    for _ in ("nifti", "scans"):
        src = pjoin(studydir, _)
        if os.path.exists(src):
            shutil.move(src, sourcedata_dir)

    niftidir = pjoin(sourcedata_dir, "nifti")
    bidsnames = config["bidsnames"]

    for scantype in bidsnames:  # ('anat', 'func')
        scantype_dir = pjoin(subject_dir, scantype)
        os.makedirs(scantype_dir, exist_ok=True)
        
        for scanname, _ in sorted(bidsnames[scantype].items(), key=lambda x: x[1]):
            scans = [
                os.path.basename(_)
                for _ in glob(pjoin(niftidir, scanname + f"*[0-9]{niigz}"))
            ]
            if not scans:
                logging.warning(f"No scans found named {scanname}.")
                continue

            multiecho = scans[0].split("_")[-1][0] == "e"

            if not keep_all_runs:
                # OLD BEHAVIOR
                sources_by_run = {0: final_scan(scans, multiecho)}
                has_repeats = False
                fid_is_sbref = {0: {}}
            else:
                # NEW BEHAVIOR: Group paired BOLD and SBRef together
                # We map a generic chronological run counter to the distinct underlying dcm2niix pairs
                bold_fids = set()
                sbref_fids = set()
                fid_to_file = {}
                file_is_sbref = {}

                for file in scans:
                    is_sbref = "_SBRef_" in file or file.split("_")[-2] == "SBRef"
                    
                    if multiecho:
                        m = re.search(rf"_(\d+)_e\d{niigz}$", file)
                    else:
                        m = re.search(rf"_(\d+){niigz}$", file)
                    
                    if m:
                        fid = int(m.group(1))
                        if fid >= 1000: 
                            continue
                        
                        if is_sbref:
                            sbref_fids.add(fid)
                        else:
                            bold_fids.add(fid)
                            
                        if fid not in fid_to_file:
                            fid_to_file[fid] = []
                        fid_to_file[fid].append(file)
                        file_is_sbref[file] = is_sbref

                # Chronologically align the bold runs. 
                # If a run lacks a companion BOLD (SBRef only), we fallback gracefully.
                sorted_bold = sorted(list(bold_fids))
                sorted_sbref = sorted(list(sbref_fids))
                
                sources_by_run = {}
                fid_is_sbref = {}
                run_idx = 1

                # Step A: Pair SBRefs with their chronological BOLD counterparts
                # SBRefs always precede or match the sequence block order
                while sorted_bold:
                    b_fid = sorted_bold.pop(0)
                    current_run_files = list(fid_to_file[b_fid])
                    
                    # Look if there is a remaining SBRef that occurred right before this BOLD sequence
                    if sorted_sbref and sorted_sbref[0] < b_fid:
                        s_fid = sorted_sbref.pop(0)
                        current_run_files.extend(fid_to_file[s_fid])
                    
                    sources_by_run[run_idx] = sorted(current_run_files)
                    fid_is_sbref[run_idx] = file_is_sbref
                    run_idx += 1
                
                # Step B: Pick up orphan SBRefs if any exist
                while sorted_sbref:
                    s_fid = sorted_sbref.pop(0)
                    sources_by_run[run_idx] = sorted(fid_to_file[s_fid])
                    fid_is_sbref[run_idx] = file_is_sbref
                    run_idx += 1

                has_repeats = len(sources_by_run) > 1

            # Loop through paired runs
            for run_idx, sources in sources_by_run.items():
                run_tag = f"run-{run_idx:02d}" if (keep_all_runs and has_repeats) else ""

                for source in sources:
                    basename = f"sub-{subject}_"
                    if session:
                        basename += f"ses-{session}_"

                    bidsbase = bidsnames[scantype][scanname]
                    
                    # Fix target suffix if it's an SBRef companion file
                    if keep_all_runs and fid_is_sbref[run_idx].get(source, False):
                        if bidsbase.endswith("_bold"):
                            bidsbase = bidsbase.replace("_bold", "_sbref")
                        elif bidsbase.endswith("bold"):
                            bidsbase = bidsbase.replace("bold", "sbref")
                        else:
                            bidsbase += "_sbref"

                    basename += bidsbase
                    pieces = basename.split("_")
                    
                    if run_tag:
                        pieces.insert(-1, run_tag)

                    if multiecho:
                        m = re.search(rf"_\d+_e(\d){niigz}$", source)
                        echobids = f"echo-{m.group(1)}"
                        pieces.insert(-1, echobids)

                    basename = "_".join(pieces)

                    logging.info(f"Copying {source} to {basename}.")
                    for extension in EXTENSIONS:
                        try:
                            os.link(
                                pjoin(niftidir, source.replace(niigz, extension)),
                                pjoin(scantype_dir, basename + extension),
                            )
                            preprocess(
                                config,
                                studydir,
                                scantype_dir,
                                basename,
                                extension,
                                bidsbase,
                            )
                        except FileNotFoundError:
                            pass
