FROM mambaorg/micromamba:latest

USER root
RUN useradd --create-home --shell /bin/bash --uid 1001 qc

RUN micromamba config set channel_alias https://anaconda.mgb.org/ && \
    micromamba config set ssl_verify false && \
    micromamba install -y -n base --override-channels -c conda-forge \
      pydicom nipype dcm2niix dcmtk && \
    micromamba clean --all --yes

ENV PATH=/opt/conda/bin:${PATH}

USER qc
ADD receiver_eostudy_qc.py /pipebin/
