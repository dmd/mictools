from os.path import join as pjoin
from nipype.interfaces.fsl import ExtractROI
import nibabel as nb
from registry import DICOMIN, registry_info, task_select
import logging

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)


def is_4D(niftifile):
    shape = nb.load(niftifile).header.get_data_shape()
    if len(shape) == 4:
        return shape[3] > 1
    else:
        return False


def trimT(in_file, roi_file, t_min=0, t_size=-1):
    ExtractROI(in_file=in_file, roi_file=roi_file, t_min=t_min, t_size=t_size).run()


def preprocess(studydir, scantype_dir, basename, extension, bidsbase):
    ris = registry_info(studydir)
    if "preprocess" not in ris:
        return
    risp = ris["preprocess"]
    logging.info(f"preprocess stanza found with sections: {' '.join(risp.keys())}")
    fname = pjoin(scantype_dir, basename + extension)

    if "trimstart" in risp:
        if not extension == ".nii.gz":
            return
        logging.info(f"trimstart stanza has: {' '.join(risp['trimstart'].keys())}")

        if bidsbase not in risp["trimstart"] and "DEFAULT" not in risp["trimstart"]:
            logging.warning(f"trimstart ignoring {fname}: no value or DEFAULT")
            return
        if not is_4D(fname):
            logging.warning(f"Rejected {fname}, not a 4D file")
            return

        # if we're here there'll be value for either bidsbase or DEFAULT
        default_t_min = risp["trimstart"].get("DEFAULT", 0)
        is_default = "" if bidsbase in risp["trimstart"] else "(DEFAULT) "
        t_min = risp["trimstart"].get(bidsbase, default_t_min)
        logging.info(f"Starting to trimT {t_min} {is_default}off {fname}")
        trimT(fname, fname, t_min)
        logging.info(f"Finished trimT")
