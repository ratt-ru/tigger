FROM radioastro/casa:4.2

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
        libicu48 \
    &&  \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ADD . /tmp/tigger

RUN cd /tmp/tigger && python setup.py install

ENTRYPOINT /usr/local/bin/tigger
