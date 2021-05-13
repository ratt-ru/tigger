#!/bin/bash
echo "Tigger v1.6.0 - Ubuntu 20.04 install script"

# install via packages by default
build_type="package"

tigger_pwd="${PWD}"

display_usage() {
	echo -e "\nUsage: $0 [OPTION]\n"
	echo -e "-s, --source     install PyQt-Qwt from source\n"
	}

# check whether user had supplied -h or --help.
if [[ ( $1 == "--help") ||  $1 == "-h" ]]
then
	display_usage
	exit 0
fi

# if source build then set build type
if [[ ( $1 == "--source") ||  $1 == "-s" ]]
then
	build_type="source"
fi

echo "Installing package dependencies..."

# install Tigger deps
sudo apt -y install python3-pyqt5.qtsvg python3-pyqt5.qtopengl &&

# install PyQt-Qwt deps
sudo apt -y install pyqt5-dev pyqt5-dev-tools python3-pyqt5 libqwt-qt5-dev libqwt-headers libqt5opengl5-dev git &&

# compile PyQt-Qwt
if [[ $build_type == "source" ]]
then
	echo "Compiling PyQt-Qwt..."
 	cd /tmp && 
 	rm -rf PyQt-Qwt && 
 	git clone https://github.com/razman786/PyQt-Qwt.git && 
 	cd PyQt-Qwt && 
 	QT_SELECT=qt5 python3 configure.py --qwt-incdir=/usr/include/qwt --qwt-libdir=/usr/lib --qwt-lib=qwt-qt5 &&  
 	make -j4 &&  
 	sudo make install && 
 	cd /tmp && 
 	cd "${tigger_pwd}"
fi

# install PyQt-Qwt package
if [[ $build_type == "package" ]]
then
	sudo dpkg -i ubuntu_20_04_deb_pkg/python3-pyqt5.qwt_2.00.00-1build1_amd64.deb
fi

# install Tigger
python3 setup.py install --user 

echo "Tigger installation complete"
