echo "Tigger - Ubuntu 20.04 install script"

tigger_pwd="${PWD}"

# install Tigger deps
sudo apt -y install python3-pyqt5.qtsvg python3-pyqt5.qtopengl &&

# install PyQt-Qwt deps
sudo apt -y install pyqt5-dev pyqt5-dev-tools python3-pyqt5 libqwt-qt5-dev libqwt-headers libqt5opengl5-dev git &&

# compile PyQt-Qwt
cd /tmp &&
git clone https://github.com/razman786/PyQt-Qwt.git &&
cd PyQt-Qwt &&
git checkout ubuntu_zoomstack &&
QT_SELECT=qt5 python3 configure.py --qwt-incdir=/usr/include/qwt --qwt-libdir=/usr/lib --qwt-lib=qwt-qt5 && 
make -j4 && 
sudo make install &&
cd /tmp &&
mv PyQt-Qwt old_PyQt-Qwt &&
cd "${tigger_pwd}" &&

# install Tigger
python3 setup.py install --user 

echo "Tigger installation complete"
