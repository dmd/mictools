#!/usr/bin/env python3
from os.path import join as pjoin
import os
import sys
import getpass
from pathlib import Path

SBATCH = "/cm/shared/apps/slurm/current/bin/sbatch"

SYSTYPE = "slurm"
SUBMITTER = SBATCH
SINGULARITY = "/cm/local/apps/apptainer/current/bin/singularity"
if os.getenv("SLURM_JOB_ID"):
    print(
        "micc_fmriprep does job submission on your behalf. "
        "Do not run it as part of a sbatch job; run it in the shell "
        "on the Mickey head node.",
        file=sys.stderr,
    )
    exit(1)


def make_runscript(args, workdir):
    """
    Create a temporary script file we can submit to qsub.
    """

    import tempfile

    if args.outputdir is None:
        args.outputdir = pjoin(args.bidsdir, "derivatives")

    pre = []
    pre += ["export APPTAINERENV_TEMPLATEFLOW_HOME=/home/fmriprep/.cache/templateflow"]
    s = []
    s += [SINGULARITY + " run"]
    s += ["--contain"]
    s += ["--cleanenv"]
    s += ["--home /home/fmriprep -B $HOME:/home/fmriprep -B $HOME:$HOME"]
    s += [
        "-B /tmp -B /data -B /data1 -B /data2 -B /data3 -B /n -B /cm/shared -B /data/fmriprep-workdir"
    ]

    s += [f"/cm/shared/singularity/images/fmriprep-{args.fmriprep_version}.simg"]
    s += [args.bidsdir]
    s += [args.outputdir]
    s += ["participant"]
    s += ["--fs-license-file /cm/shared/freesurfer-license.txt"]
    s += [f"--participant_label {args.participant}"]

    if isinstance(args.output_spaces, str):
        s += [f"--output-spaces {args.output_spaces}"]
    if isinstance(args.output_spaces, list):
        s += [f"--output-spaces {' '.join(args.output_spaces)}"]

    s += [f"--n_cpus {args.ncpus}"]
    s += [f"--mem-mb {args.ramsize*1024}"]
    s += ["--notrack"]

    if "dummy_scans" in args and args.dummy_scans is not None:
        s += [f"--dummy-scans {args.dummy_scans}"]

    if args.ignore:
        s += ["--ignore " + " ".join(args.ignore)]

    if args.aroma:
        s += ["--use-aroma"]

    if args.force_syn:
        # Check if fmriprep version is 25 or newer
        if (
            args.fmriprep_version
            and args.fmriprep_version[:2].isdigit()
            and int(args.fmriprep_version[:2]) >= 25
        ):
            s += ["--force syn-sdc"]
        else:
            s += ["--force-syn"]

    if not args.disable_syn_sdc:
        s += ["--use-syn-sdc"]

    if args.anat_only:
        s += ["--anat-only"]

    if args.skip_bids_validation:
        s += ["--skip-bids-validation"]

    if not args.freesurfer:
        s += ["--fs-no-reconall"]

    if args.longitudinal:
        s += ["--longitudinal"]

    if args.return_all_components:
        s += ["--return-all-components"]

    if args.me_output_echos:
        s += ["--me-output-echos"]

    if args.topup_max_vols:
        s += [f"--topup-max-vols {args.topup_max_vols}"]

    if args.anat_derivatives:
        s += [f"--anat-derivatives {args.anat_derivatives}"]

    if args.bids_filter_file:
        s += [f"--bids-filter-file {args.bids_filter_file}"]

    if args.fs_subjects_dir:
        s += [f"--fs-subjects-dir {args.fs_subjects_dir}"]

    if args.cifti_output:
        s += [f"--cifti-output {args.cifti_output}"]

    if args.me_t2s_fit_method:
        s += [f"--me-t2s-fit-method {args.me_t2s_fit_method}"]

    if args.verbose:
        s += ["-vvvv"]
    else:
        s += ["-vv"]

    if workdir != "__EMPTY__":
        s += [f"-w  {workdir}"]

    script = "#!/bin/bash\n\n" + "\n".join(pre) + "\n" + " \\\n    ".join(s) + "\n"

    if args.email:
        script += f"""echo "fMRIPrep job ended (successfully or not).
Host: $(hostname)
Job ID: $SLURM_JOB_ID
Job Name: $SLURM_JOB_NAME
BIDS dir: {args.bidsdir}
" | mail -S sendwait -s "fMRIprep job $SLURM_JOB_ID ended" {args.email}

"""

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
        "--email",
        help="Email you at given address when the job ends (successfully or not). (Default: off)",
    )

    parser.add_argument(
        "--aroma",
        help="Turn on AROMA processing (in fMRIprep <23.1). (Default: off)",
        action="store_true",
    )

    parser.add_argument(
        "--disable-syn-sdc",
        help="Turn OFF synthetic field map correction. (Default: on)",
        action="store_true",
    )

    parser.add_argument(
        "--force-syn",
        help="Use SyN correction in addition to fieldmap correction. (Default: off)",
        action="store_true",
    )

    parser.add_argument(
        "--ignore",
        action="store",
        nargs="+",
        choices=["fieldmaps", "slicetiming", "sbref"],
        help="Ignore selected aspects of the input dataset to disable corresponding "
        "parts of the workflow (a space delimited list)",
    )

    parser.add_argument(
        "--me-output-echos",
        help="Enable additional outputs during multiecho processing.",
        action="store_true",
    )

    parser.add_argument(
        "--topup-max-vols",
        help="Adjust processing of TOPUP scans.",
        type=int,
        metavar="TOPUP_MAX_VOLS",
    )

    parser.add_argument(
        "--anat-derivatives",
        help="Reuse a preexisting anatomic analysis.",
        metavar="PATH",
    )

    parser.add_argument(
        "--bids-filter-file",
        help="A JSON file describing custom BIDS input filters using PyBIDS.",
        metavar="FILE",
    )

    parser.add_argument(
        "--fs-subjects-dir",
        help="Path to existing FreeSurfer subjects directory to reuse.",
        metavar="PATH",
    )

    parser.add_argument(
        "--ncpus", help="Number of threads and cores. (Default: 8)", type=int, default=8
    )

    parser.add_argument(
        "--dummy-scans", help="Number of dummy scans. (Default: 0)", type=int
    )

    parser.add_argument(
        "--ramsize", help="RAM size to use, in GB. (Default: 32)", type=int, default=32
    )

    parser.add_argument(
        "--skip-bids-validation", help="Skip BIDS validation.", action="store_true"
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
        '(Default: "MNI152NLin2009cAsym:res-2 MNI152NLin6Asym:res-2 anat func fsaverage")',
        nargs="*",
        default="MNI152NLin2009cAsym:res-2 MNI152NLin6Asym:res-2 anat func fsaverage",
    )

    parser.add_argument(
        "--cifti-output",
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--me-t2s-fit-method",
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--outputdir",
        help='Output directory. (Default: "derivatives" in BIDS dir)',
        action=FullPaths,
    )

    parser.add_argument(
        "--jobname",
        help='Name of the job in the job scheduler. (Default: "fmriprep")',
        default="fmriprep",
    )

    parser.add_argument(
        "--dry-run",
        help="Do not actually submit the job; just show what would be submitted.",
        action="store_true",
    )

    parser.add_argument(
        "--logs",
        help="Where to write logs to. (Default: current directory)",
        action=FullPaths,
        type=is_dir,
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
        help="FORCE the work directory instead of using the default of /data/fmriprep-workdir/USERNAME. "
        "Please do not use this unless you must. "
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

    workdir_group.add_argument(
        "--workdir-user-subdir",
        help="Rather than using /data/fmriprep-workdir/USERNAME, use a subdirectory of that with the supplied name. "
        "This flag is used by iris-fmriprep to ensure that multiple runs "
        "of the same subject, but different sessions, do not collide.",
    )

    versioning.add_argument(
        "--fmriprep-version",
        help="fmriprep version number. Default: 25.2-latest",
        default="25.2-latest",
    )

    args = parser.parse_args()

    if not os.path.exists(
        f"/cm/shared/singularity/images/fmriprep-{args.fmriprep_version}.simg"
    ):
        print(
            f"The cluster does not have fmriprep version {args.fmriprep_version} installed."
        )
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
            "--workdir is no longer valid.\nBy default, micc_fmriprep will "
            "use /data/fmriprep-workdir/USERNAME.\nIf you need to force a different "
            "location, use --force-workdir."
        )
        sys.exit(1)

    if args.force_workdir:
        workdir = args.force_workdir
    elif args.no_workdir:
        workdir = "__EMPTY__"
    elif args.workdir_user_subdir:
        workdir = pjoin(
            "/data/fmriprep-workdir", getpass.getuser(), args.workdir_user_subdir
        )
    else:
        workdir = pjoin("/data/fmriprep-workdir", getpass.getuser())

    if Path(args.bidsdir) in Path(workdir).parents or args.bidsdir == workdir:
        print("Your workdir cannot be in your BIDS dir.")
        sys.exit(1)

    if args.logs:
        logsdir = args.logs
    else:
        logsdir = "."

    filename, script = make_runscript(args, workdir)
    action = "NOT submitting" if args.dry_run else "Submitting"
    print(f"{action} {filename} to {SYSTYPE}, the contents of which are:")
    print("================")
    print(script)
    print("================")

    sub_cmd = f"{SBATCH} --job-name {args.jobname} --output={logsdir}/%x-%j.out --error={logsdir}/%x-%j.err --time 1-4 --cpus-per-task={args.ncpus} --mem={int(args.ramsize*1.25)}G {filename}".split()
    print(" ".join(sub_cmd))
    if args.dry_run:
        print("NOT running; dry run only.")
    else:
        proc = subprocess.Popen(
            sub_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        stdout, stderr = proc.communicate()
        print("stdout:\n")
        print(stdout)
        print("\n\nstderr:")
        print(stderr)
    # os.unlink(filename)
