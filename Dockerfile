FROM kernsuite/base:2

MAINTAINER gijsmolenaar@gmail.com
# TODO - this will need updating to PyQt5, see installation script.
RUN docker-apt-install \
    python-qt4 \
    python-qwt5-qt4

ADD . /tmp/tigger

RUN pip install /tmp/tigger

CMD /usr/local/bin/tigger
