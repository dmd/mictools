FROM conda/miniconda3-centos7
MAINTAINER ddrucker@mclean.harvard.edu

# the finisher needs access to the host's uids/gids so it can chown
# here at the MIC we use LDAP.
# therefore we install nss-pam-ldapd and run with:
# -v /etc/nsswitch.conf:/etc/nsswitch.conf:ro
# -v /var/run/nslcd/socket:/var/run/nslcd/socket:ro

RUN yum -y install nss-pam-ldapd pigz

RUN conda install -y -c conda-forge \
             pyyaml \
             pydicom \
             nipype \
             dcm2niix

ADD finish_pipe.py \
     registry.py \
     run_pipeline_parts.py \
     sub_ses_matcher.py \
     receiver_eostudy.py \
     /miccpipe/

