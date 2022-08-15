FROM pydicom/dicom

RUN apt-get update --allow-releaseinfo-change
RUN apt-get install unzip
RUN wget https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20220720/dcm2niix_lnx.zip
RUN unzip dcm2niix_lnx.zip
RUN mv dcm2niix /usr/bin/

ADD studylen.py /
ADD spectrorename /
ADD gapfinder.py /
