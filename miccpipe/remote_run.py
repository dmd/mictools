# Note: this is a bad idea, and I am a bad person for doing it.
# It does some basic security checks but is still probably awful.
#
# Problem: I want to be able to submit fmriprep jobs (or other tasks)
# to the cluster *from inside a container*.
#
# I do not want to install SGE in the container.
# I do not want to do any awful hacks where I try to pretend I'm the head
# node inside the container.
#
# So, I'm just going to let the container create a script file
# as the pipeline user, and then have a daemon (running as that user)
# accept a POST which will tell it to execute that file.
#
# This is that daemon.
#
# Note that it really expects something that is going to run qsub
# and return a job id.

from flask import Flask, request, jsonify
from urllib.parse import parse_qs
import ipaddress
from os.path import basename, join as pjoin
import os
import subprocess
import pwd
import grp
import re
from registry import DICOMIN
from run_pipeline_parts import colors
from finish_pipe import fmriprep_running

app = Flask(__name__)

allowed = "172.17.0.0/24"
rundir = pjoin(DICOMIN, "run")
randir = pjoin(DICOMIN, "ran")


def perms(filename):
    s = os.stat(filename)
    u = pwd.getpwuid(s.st_uid).pw_name
    g = grp.getgrgid(s.st_gid).gr_name
    p = oct(s.st_mode)[-3:]
    return (u, g, p)


@app.route("/jobstatus", methods=["GET"])
def jobstatus():
    if "studydir" not in request.args:
        return jsonify({"info": "studydir key not found"}), 500
    studydir = request.args["studydir"]
    return jsonify({"running": fmriprep_running(studydir)}), 200


@app.route("/jobsubmit", methods=["POST"])
def submitsge():
    if "cmdfile" not in request.form:
        return jsonify({"info": "cmdfile key not found"}), 500
    if "studydir" not in request.form:
        return jsonify({"info": "studydir key not found"}), 500
    if ipaddress.ip_address(request.remote_addr) not in ipaddress.ip_network(allowed):
        return jsonify({"info": "forbidden from your IP"}), 500

    cmd = basename(request.form["cmdfile"])
    studydir = request.form["studydir"]

    runcmd = pjoin(rundir, cmd)

    if not os.path.exists(runcmd):
        return jsonify({"info": "cmdfile value does not exist in run dir"}), 500

    if perms(runcmd) != ("pipeline", "pipeline", "700") or perms(rundir) != (
        "pipeline",
        "pipeline",
        "700",
    ):
        return jsonify({"info": "suspicious permissions found"}), 500

    proc = subprocess.Popen(
        open(runcmd).read().split("\0"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    stdout, stderr = proc.communicate()
    if b"has been submitted" in stdout:
        job_id = re.search(r"Your job (\d{6})", str(stdout)).group(1)
        open(pjoin(studydir, ".pipe_sgejobid"), "w").write(job_id)
        return (
            jsonify(
                {
                    "info": f"run {cmd} from {request.remote_addr}",
                    "stdout": stdout,
                    "stderr": stderr,
                    "sgejobid": job_id,
                }
            ),
            200,
        )
    else:
        return jsonify({"stdout": stdout, "stderr": stderr, "info": "error"}), 500


#        os.rename(runcmd, pjoin(randir, cmd))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=11052)
