FROM conda/miniconda3-centos7
MAINTAINER ddrucker@mclean.harvard.edu

ENV FSLOUTPUTTYPE NIFTI_GZ
ENV INSIDE_DOCKER yes

# the finisher needs access to the host's uids/gids so it can chown
# here at the MIC we use LDAP.
# therefore we install nss-pam-ldapd and run with:
# -v /etc/nsswitch.conf:/etc/nsswitch.conf:ro
# -v /var/run/nslcd/socket:/var/run/nslcd/socket:ro

RUN yum install -y epel-release && yum -y install openssh-clients nss-pam-ldapd pigz wget openblas-devel

RUN conda install -y -c conda-forge \
             pyyaml \
             pydicom \
             nipype \
             dcm2niix

RUN mkdir /miccpipe

# defacing tools
RUN wget -N -qO- -O /miccpipe/mri_deface \
  ftp://surfer.nmr.mgh.harvard.edu/pub/dist/mri_deface/mri_deface_linux && \
  chmod +x /miccpipe/mri_deface

RUN wget -N -qO- -O /miccpipe/face.gca.gz \
  ftp://surfer.nmr.mgh.harvard.edu/pub/dist/mri_deface/face.gca.gz && \
  gunzip /miccpipe/face.gca.gz

RUN wget -N -qO- -O /miccpipe/talairach_mixed_with_skull.gca.gz \
  ftp://surfer.nmr.mgh.harvard.edu/pub/dist/mri_deface/talairach_mixed_with_skull.gca.gz && \
  gunzip /miccpipe/talairach_mixed_with_skull.gca.gz

# if this step fails, perhaps you didn't run make--
# the Makefile copies what's needed from your FSL install
ADD finish_pipe.py \
     registry.py \
     run_pipeline_parts.py \
     sub_ses_matcher.py \
     receiver_eostudy.py \
     preprocess.py \
     flirt \
     fslmaths \
     fslroi \
     eye.mat \
     /miccpipe/

ENV PATH="/miccpipe:${PATH}"
