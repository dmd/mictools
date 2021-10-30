#!/usr/bin/env python3
from os.path import expanduser, join as pjoin
import os
import sys
import getpass
from pathlib import Path

QSUB = "/cm/shared/apps/sge/2011.11p1/bin/linux-x64/qsub"


def make_runscript(args, workdir):
    """
    Create a temporary script file we can submit to qsub.
    """

    import tempfile

    if args.outputdir is None:
        args.outputdir = pjoin(args.bidsdir, "derivatives")

    pre = []
    pre += [
        "export SINGULARITYENV_TEMPLATEFLOW_HOME=/home/fmriprep/.cache/templateflow"
    ]
    s = []
    s += ["/usr/bin/singularity run"]
    s += ["--contain"]
    s += ["--cleanenv"]
    s += ["-B /tmp -B /data -B /data1 -B /data2 -B /data3 -B /cm/shared"]

    s += [f"/cm/shared/singularity/images/fmriprep-{args.fmriprep_version}.simg"]
    s += [args.bidsdir]
    s += [args.outputdir]
    s += ["participant"]
    s += ["--fs-license-file /cm/shared/freesurfer-6.0.1/license.txt"]
    s += [f"--participant_label {args.participant}"]

    if isinstance(args.output_spaces, str):
        s += [f"--output-spaces {args.output_spaces}"]
    if isinstance(args.output_spaces, list):
        s += [f"--output-spaces {' '.join(args.output_spaces)}"]

    s += [f"--n_cpus {args.ncpus}"]
    s += [f"--mem-mb {args.ramsize*1024}"]
    s += ["--notrack"]

    if args.dummy_scans != 0:
        s += [f"--dummy-scans {args.dummy_scans}"]

    if args.ignore:
        s += ["--ignore " + " ".join(args.ignore)]

    if args.aroma:
        s += ["--use-aroma"]

    if not args.disable_syn_sdc:
        s += ["--use-syn-sdc"]

    if args.anat_only:
        s += ["--anat-only"]

    if args.skip_bids_validation:
        s += ["--skip_bids_validation"]

    if not args.freesurfer:
        s += ["--fs-no-reconall"]

    if args.longitudinal:
        s += ["--longitudinal"]

    if args.return_all_components:
        s += ["--return-all-components"]

    if args.verbose:
        s += ["-vvvv"]
    else:
        s += ["-vv"]

    if workdir != "__EMPTY__":
        s += [f"-w  {workdir}"]

    script = "#!/bin/bash\n\n" + "\n".join(pre) + "\n" + " \\\n    ".join(s) + "\n"

    _, filename = tempfile.mkstemp()
    with open(filename, "w") as fp:
        fp.write(script)
    return filename, script


if __name__ == "__main__":
    import subprocess
    import argparse

    class FullPaths(argparse.Action):
        """Expand user- and relative-paths"""

        def __call__(self, parser, namespace, values, option_string=None):
            if values == "":
                setattr(namespace, self.dest, "__EMPTY__")
            else:
                setattr(
                    namespace, self.dest, os.path.abspath(os.path.expanduser(values))
                )

    def is_dir(dirname):
        """Checks if a path is an actual directory"""
        if not os.path.isdir(dirname):
            msg = "{0} is not a directory".format(dirname)
            raise argparse.ArgumentTypeError(msg)
        else:
            return dirname

    parser = argparse.ArgumentParser(
        description="Run fMRIPrep, with some MIC cluster specific presets."
    )

    required = parser.add_argument_group("required arguments")
    workdir_group = parser.add_mutually_exclusive_group()
    versioning = parser.add_argument_group("Version")

    parser.add_argument(
        "--aroma", help="Turn on AROMA processing. (Default: off)", action="store_true"
    )

    parser.add_argument(
        "--disable-syn-sdc",
        help="Turn OFF synthetic field map correction. (Default: on)",
        action="store_true",
    )

    parser.add_argument(
        "--ignore",
        action="store",
        nargs="+",
        choices=["fieldmaps", "slicetiming", "sbref"],
        help="ignore selected aspects of the input dataset to disable corresponding "
        "parts of the workflow (a space delimited list)",
    )

    parser.add_argument(
        "--ncpus", help="Number of threads and cores. (Default: 4)", type=int, default=4
    )

    parser.add_argument(
        "--dummy-scans", help="Number of dummy scans. (Default: 0)", type=int, default=0
    )

    parser.add_argument(
        "--ramsize", help="RAM size to use, in GB. (Default: 8)", type=int, default=8
    )

    parser.add_argument(
        "--skip_bids_validation", help="Skip BIDS validation.", action="store_true"
    )

    parser.add_argument(
        "--freesurfer",
        help="Enable FreeSurfer processing. (Default: off)",
        action="store_true",
    )

    parser.add_argument(
        "--longitudinal",
        help="Enable longitudinal anatomic processing (this will increase run time). (Default: off)",
        action="store_true",
    )

    parser.add_argument(
        "--anat-only",
        help="Do only anatomical processing - no fMRI.",
        action="store_true",
    )

    parser.add_argument(
        "--return-all-components",
        help="Include all components estimated in CompCor decomposition in the confounds file. (Default: off)",
        action="store_true",
    )

    parser.add_argument(
        "--output-spaces",
        help="Specify the output space(s), as a space-separated list. "
        '(Default: "MNI152NLin2009cAsym:res-2 anat func fsaverage")',
        nargs="*",
        default="MNI152NLin2009cAsym:res-2 anat func fsaverage",
    )

    parser.add_argument(
        "--outputdir",
        help='Output directory. (Default: "derivatives" in BIDS dir)',
        action=FullPaths,
    )

    parser.add_argument(
        "--jobname",
        help='Name of the SGE job. (Default: "fmriprep")',
        default="fmriprep",
    )

    parser.add_argument(
        "--dry-run",
        help="Do not actually submit the job; just show what would be submitted.",
        action="store_true",
    )

    parser.add_argument(
        "--verbose", help="Verbose logging, for debugging.", action="store_true"
    )

    required.add_argument(
        "--bidsdir",
        help="BIDS directory.",
        required=True,
        action=FullPaths,
        type=is_dir,
    )

    required.add_argument(
        "--participant", help="Participant label.", required=True, type=str
    )

    workdir_group.add_argument(
        "--force-workdir",
        help="FORCE the work directory instead of using the MICC default of /data/fmriprep-workdir/USERNAME"
        "Please do not use this unless you must."
        "This directory must not be inside your BIDS dir.",
        action=FullPaths,
    )

    workdir_group.add_argument(
        "--workdir",
        help=argparse.SUPPRESS,
    )

    workdir_group.add_argument(
        "--no-workdir",
        help="Do not use a workdir at all.",
        action="store_true",
    )

    versioning.add_argument(
        "--fmriprep-version",
        help="fmriprep version number. Default: 20.2.6",
        default="20.2.6",
    )

    args = parser.parse_args()

    if not os.path.exists(
        f"/cm/shared/singularity/images/fmriprep-{args.fmriprep_version}.simg"
    ):
        print(f"MICC does not have fmriprep version {args.fmriprep_version} installed.")
        sys.exit(1)

    # apparently fmriprep has trouble if you run this from inside BIDS dir
    if (
        Path(args.bidsdir) in Path(os.getcwd()).parents
        or os.getcwd() == args.bidsdir
        or os.path.exists(pjoin(os.getcwd(), "dataset_description.json"))
    ):
        print("fmriprep currently messes up if you run it from inside the BIDS dir.")
        print("Run this script from somewhere else instead, like your $HOME directory.")
        sys.exit(1)

    if args.workdir:
        print(
            "The --workdir argument is no longer valid.\nBy default, micc_fmriprep will "
            "use /data/fmriprep-workdir/USERNAME.\nIf you need to force a different "
            "location, use --force-workdir."
        )
        sys.exit(1)

    if args.force_workdir:
        workdir = args.force_workdir
    elif args.no_workdir:
        workdir = "__EMPTY__"
    else:
        workdir = pjoin("/data/fmriprep-workdir", getpass.getuser())

    if Path(args.bidsdir) in Path(workdir).parents or args.bidsdir == workdir:
        print("Your workdir cannot be in your BIDS dir.")
        sys.exit(1)

    filename, script = make_runscript(args, workdir)
    action = "NOT submitting" if args.dry_run else "Submitting"
    print(f"{action} {filename} to qsub, the contents of which are:")
    print("================")
    print(script)
    print("================")

    qsub_cmd = f"{QSUB} -cwd -q fmriprep.q -N {args.jobname} -pe fmriprep {args.ncpus} -w e -R y {filename}".split()
    print(" ".join(qsub_cmd))
    if args.dry_run:
        print("NOT running; dry run only.")
    else:
        proc = subprocess.Popen(
            qsub_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        stdout, stderr = proc.communicate()
        print("stdout:\n")
        print(stdout)
        print("\n\nstderr:")
        print(stderr)
    # os.unlink(filename)
