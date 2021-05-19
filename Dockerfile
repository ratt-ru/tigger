FROM kernsuite/base:7

RUN docker-apt-install xvfb python3-pip

ADD . /tmp/tigger

WORKDIR /tmp/tigger

RUN apt update && ./install_tigger_ubuntu.sh -ns -dai
# basic test to open the gui in a virtual buffer for a few seconds to see if it loads up successfully
# if fits and catalog loads successfully and no exceptions are raised in timeout number of seconds then we deem 
# the integration test successful
ENV Xtimeout=10s
RUN echo "\n\n*******************************\n Integration Test \n*******************************\n"; \
    echo "Starting X11 Virtual Frame Buffer and waiting for ${Xtimeout} for Tigger to load and run\n\n" && \
    xvfb-run --server-args='-screen 0 1024x768x24' \
    timeout ${Xtimeout} \
    $(which python3) -u \
    /root/.local/bin/tigger /tmp/tigger/test-files/cat.gaul /tmp/tigger/test-files/star_model_image.fits > /tmp/tigger.log 2>&1; \
    (test $? -eq 124 && \
     cat /tmp/tigger.log && \
     cat /tmp/tigger.log | grep "Welcome to Tigger" > /dev/null && \
     cat /tmp/tigger.log | grep "Please wait a second while the GUI starts up" > /dev/null && \
     cat /tmp/tigger.log | grep "Loaded 17 sources from 'Gaul' file /tmp/tigger/test-files/cat.gaul" > /dev/null && \
     cat /tmp/tigger.log | grep "Loaded FITS image /tmp/tigger/test-files/star_model_image.fits" > /dev/null && \
     cat /tmp/tigger.log | grep -v "Exception" > /dev/null && \
     cat /tmp/tigger.log | grep -v "Error" > /dev/null && \
     cat /tmp/tigger.log | grep -v "Problem" > /dev/null && \
     cat /tmp/tigger.log | grep -v "Bug" > /dev/null && \
     cat /tmp/tigger.log | grep -v "bug" > /dev/null && \
     echo "\n\nOutput looks ok as far as we can tell" &&\
     echo "\n\n*******************************\n Integration Test Passed \n*******************************"\
    ) || (echo "\n\n*******************************\n Integration Test Failed \n*******************************" && exit 1)
ENTRYPOINT .local/bin/tigger
