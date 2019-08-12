#!/cm/shared/anaconda3/bin/python3

QSUB = '/cm/shared/apps/sge/2011.11p1/bin/linux-x64/qsub'


def make_runscript(args):
    """
    Create a temporary script file we can submit to qsub.
    """

    import tempfile

    s = []
    s += ['/cm/shared/singularity/bin/singularity run']
    s += ['--cleanenv']
    s += ['-B /data:/data -B /data1:/data1 -B /data2:/data2 -B /data3:/data3 -B /cm/shared:/cm/shared']
    s += [args.fmriprep_container]
    s += [f'--fs-license-file /cm/shared/freesurfer-6.0.1/license.txt']
    s += [f'-w  {args.workdir}']
    s += [f'--participant_label {args.participant}']
    s += [f'--output-spaces {args.output_spaces}']
    s += [f'--n_cpus {args.ncpus} --nthreads {args.ncpus} --omp-nthreads {args.ncpus}']
    s += [f'--mem-mb {args.ramsize*1024}']

    if args.aroma:
        s += ['--use-aroma --ignore-aroma-denoising-errors']

    if not args.disable_syn_sdc:
        s += ['--use-syn-sdc']

    if args.anat_only:
        s += ['--anat-only']

    if not args.freesurfer:
        s += ['--fs-no-reconall']

    s += [args.bidsdir]
    s += [args.outputdir]
    s += ['participant']

    script = '#!/bin/bash\n' + ' \\\n'.join(s) + '\n'

    _, filename = tempfile.mkstemp()
    with open(filename, 'w') as fp:
        fp.write(script)
    return filename, script


if __name__ == '__main__':
    import subprocess
    import os
    import argparse

    class FullPaths(argparse.Action):
        """Expand user- and relative-paths"""

        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, os.path.abspath(os.path.expanduser(values)))

    def is_dir(dirname):
        """Checks if a path is an actual directory"""
        if not os.path.isdir(dirname):
            msg = "{0} is not a directory".format(dirname)
            raise argparse.ArgumentTypeError(msg)
        else:
            return dirname


    parser = argparse.ArgumentParser(description='Run fMRIPrep, with some MIC cluster specific presets.')

    required = parser.add_argument_group('required arguments')
    donttouch = parser.add_argument_group("You don't need to touch these")

    parser.add_argument('--aroma',
                        help='Turn on AROMA processing. (Default: off)',
                        action='store_true')

    parser.add_argument('--disable-syn-sdc',
                        help='Turn OFF synthetic field map correction. (Default: on)',
                        action='store_true')

    parser.add_argument('--ncpus',
                        help='Number of threads and cores. (Default: 4)',
                        type=int,
                        default=4)

    parser.add_argument('--ramsize',
                        help='RAM size to use, in GB. (Default: 8)',
                        type=int,
                        default=8)

    parser.add_argument('--freesurfer',
                        help='Enable FreeSurfer processing. (Default: off)',
                        action='store_true')

    parser.add_argument('--anat-only',
                        help='Do only anatomical processing - no fMRI.',
                        action='store_true')

    parser.add_argument('--output-spaces',
                        help='Specify the output space. Enclose it in double quotes.'
                             'Default: "MNI152NLin6Asym:res-2 anat func fsaverage"',
                        default='MNI152NLin6Asym:res-2 anat func fsaverage')

    required.add_argument('--bidsdir',
                          help='BIDS directory.',
                          required=True,
                          action=FullPaths,
                          type=is_dir)

    required.add_argument('--outputdir',
                          help='Output directory.',
                          required=True,
                          action=FullPaths)

    required.add_argument('--workdir',
                          help='Work directory.',
                          required=True,
                          action=FullPaths)

    required.add_argument('--participant',
                          help='Participant label.',
                          required=True,
                          type=str)

    donttouch.add_argument('--fmriprep-container',
                           help='Path to the fMRIPrep container. '
                                'Default: "/cm/shared/singularity/images/fmriprep-1.4.1.simg"',
                           default='/cm/shared/singularity/images/fmriprep-1.4.1.simg')

    args = parser.parse_args()

    filename, script = make_runscript(args)
    print(f'Submitting {filename} to qsub, the contents of which are:')
    print('================')
    print(script)
    print('================')

    qsub_cmd = f'{QSUB} -q bigmem.q -N fmriprep -pe fmriprep {args.ncpus} -w e -R y {filename}'.split()
    print(qsub_cmd)
    proc = subprocess.Popen(qsub_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    stdout, stderr = proc.communicate()
    print('stdout:\n')
    print(stdout)
    print('\n\nstderr:')
    print(stderr)
    # os.unlink(filename)
