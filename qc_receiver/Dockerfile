FROM pydicom/dicom
MAINTAINER ddrucker@mclean.harvard.edu

RUN useradd --create-home --shell /bin/bash --uid 1001 qc
RUN conda install -y -c conda-forge pydicom nipype dcm2niix
USER qc
ADD receiver_eostudy_qc.py /pipebin/
