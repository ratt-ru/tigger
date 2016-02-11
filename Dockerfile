FROM radioastro/base:0.2

MAINTAINER gijsmolenaar@gmail.com

RUN apt-get update && \
    apt-get install -y \
        python-kittens \
        python-pyfits \
        python-astlib \
        python-scipy \
        python-numpy \
        python-qt4 \
        python-qwt5-qt4 \
        python-setuptools \
        python-pip \
        libicu52 \
        lofar \
    &&  \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ADD . /tmp/tigger

RUN cd /tmp/tigger && pip install .

CMD /usr/local/bin/tigger
