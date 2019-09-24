#!/usr/bin/env python3
from os.path import expanduser, join as pjoin
import os
import sys
from pathlib import Path

QSUB = "/cm/shared/apps/sge/2011.11p1/bin/linux-x64/qsub"
cachedir = expanduser("~/.cache/fmriprep")


def make_runscript(args):
    """
    Create a temporary script file we can submit to qsub.
    """

    import tempfile

    if args.outputdir is None:
        args.outputdir = pjoin(args.bidsdir, "derivatives")

    pre = []
    # re += ["export SINGULARITYENV_https_proxy=http://micc:8899"]
    pre += [
        "export SINGULARITYENV_TEMPLATEFLOW_HOME=/home/fmriprep/.cache/templateflow"
    ]

    s = []
    s += ["/cm/shared/singularity/bin/singularity run"]
    s += [
        "-B /data:/data -B /data1:/data1 -B /data2:/data2 -B /data3:/data3 -B /cm/shared:/cm/shared"
    ]
    # s += ["-B /data/TemplateFlow:/data/TemplateFlow"]

    # should be able to remove this when https://github.com/poldracklab/fmriprep/issues/1777 resolved
    s += [f"-B {cachedir}:/home/fmriprep/.cache/fmriprep"]

    s += ["--cleanenv"]
    s += [args.fmriprep_container]
    s += [args.bidsdir]
    s += [args.outputdir]
    s += ["participant"]
    s += ["--fs-license-file /cm/shared/freesurfer-6.0.1/license.txt"]
    s += [f"--participant_label {args.participant}"]
    s += [f'--output-spaces "{args.output_spaces}"']
    s += [f"--n_cpus {args.ncpus}"]
    s += [f"--mem-mb {args.ramsize*1024}"]
    s += ["--notrack"]

    # workaround FIXME
    # s += ["--use-plugin /data/ddrucker/workaround.yml"]

    if args.aroma:
        s += ["--use-aroma --ignore-aroma-denoising-errors"]

    if not args.disable_syn_sdc:
        s += ["--use-syn-sdc"]

    if args.anat_only:
        s += ["--anat-only"]

    if not args.freesurfer:
        s += ["--fs-no-reconall"]

    if args.verbose:
        s += ["-vvvv"]

    if args.workdir != "__EMPTY__":
        s += [f"-w  {args.workdir}"]

    script = "#!/bin/bash\n\n" + "\n".join(pre) + "\n" + " \\\n    ".join(s) + "\n"

    _, filename = tempfile.mkstemp()
    with open(filename, "w") as fp:
        fp.write(script)
    return filename, script


if __name__ == "__main__":
    import subprocess
    import os
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
    donttouch = parser.add_argument_group("You don't need to touch these")

    parser.add_argument(
        "--aroma", help="Turn on AROMA processing. (Default: off)", action="store_true"
    )

    parser.add_argument(
        "--disable-syn-sdc",
        help="Turn OFF synthetic field map correction. (Default: on)",
        action="store_true",
    )

    parser.add_argument(
        "--ncpus", help="Number of threads and cores. (Default: 4)", type=int, default=4
    )

    parser.add_argument(
        "--ramsize", help="RAM size to use, in GB. (Default: 8)", type=int, default=8
    )

    parser.add_argument(
        "--freesurfer",
        help="Enable FreeSurfer processing. (Default: off)",
        action="store_true",
    )

    parser.add_argument(
        "--anat-only",
        help="Do only anatomical processing - no fMRI.",
        action="store_true",
    )

    parser.add_argument(
        "--output-spaces",
        help="Specify the output space. Enclose it in double quotes. "
        '(Default: "MNI152NLin2009cAsym:res-2 anat func fsaverage")',
        default="MNI152NLin2009cAsym:res-2 anat func fsaverage",
    )

    parser.add_argument(
        "--outputdir",
        help='Output directory. (Default: "derivatives" in BIDS dir)',
        action=FullPaths,
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
        "--workdir",
        help='Work directory. Set to "" (empty string) to disable. '
        "This directory must not be inside your BIDS dir.",
        required=True,
        action=FullPaths,
    )

    required.add_argument(
        "--participant", help="Participant label.", required=True, type=str
    )

    donttouch.add_argument(
        "--fmriprep-container",
        help="Path to the fMRIPrep container. "
        'Default: "/cm/shared/singularity/images/fmriprep-1.5.0.simg"',
        default="/cm/shared/singularity/images/fmriprep-1.5.0.simg",
    )

    args = parser.parse_args()

    os.makedirs(cachedir, exist_ok=True)
    # FIXME
    # apparently fmriprep has trouble if you run this from inside BIDS dir
    if (
        Path(args.bidsdir) in Path(os.getcwd()).parents
        or os.getcwd() == args.bidsdir
        or os.path.exists(pjoin(os.getcwd(), "dataset_description.json"))
    ):
        print("fmriprep currently messes up if you run it from inside the BIDS dir.")
        print("Run this script from somewhere else instead, like your $HOME directory.")
        sys.exit(1)

    if Path(args.bidsdir) in Path(args.workdir).parents or args.bidsdir == args.workdir:
        print("Your workdir cannot be in your BIDS dir.")
        sys.exit(1)

    filename, script = make_runscript(args)
    action = "NOT submitting" if args.dry_run else "Submitting"
    print(f"{action} {filename} to qsub, the contents of which are:")
    print("================")
    print(script)
    print("================")

    qsub_cmd = f"{QSUB} -cwd -q bigmem.q -N fmriprep -pe fmriprep {args.ncpus} -w e -R y {filename}".split()
    print(qsub_cmd)
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
