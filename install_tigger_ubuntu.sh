#!/bin/bash
echo "==== Tigger v1.6.0 - Ubuntu 20.04 install script ===="

# install via packages by default
build_type="package"
install_type="normal"

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

# if source build selected then set build type
if [[ ( $1 == "--source") ||  $1 == "-s" ]]
then
	build_type="source"
fi

# identify if running on Ubuntu and which version
if [[ -n "$(command -v lsb_release)" ]]
then
	distro_name=$(lsb_release -s -d|awk '{print $1}')

	if [[ $distro_name == "Ubuntu" ]]
	then
		distro_version=$(lsb_release -rs)
	else
		echo "==== Error: Ubuntu Linux not detected, stopping installation ===="
		exit 1
	fi
else
	echo "==== Error: Unable to detect Linux distribution, stopping installation ===="
	exit 1
fi

echo "==== Installer has detected Linux distribution as $distro_name $distro_version ==== "

# check and install pip3 if needed
if command -v pip3 > /dev/null 
then
	echo "==== Installer found pip3... ===="
else
	echo "==== Installer did not find pip3... ===="
	install_type="fullstack"
	sudo apt -y install python3-setuptools python3-pip 
fi

# check for astro-tigger-lsm
tigger_lsm=`pip3 list|grep astro-tigger-lsm|awk '{print $1}'`
if [[ $tigger_lsm == "astro-tigger-lsm" ]]
then
	echo "==== Installer found astro-tigger-lsm dependency... ===="
	tigger_lsm_verison=`pip3 list|grep astro-tigger-lsm|awk '{print $2}'|sed -e 's/\.//g'`
	if [[ "$tigger_lsm_version" -lt "170" ]]
	then
		echo "==== Installer fullstack mode - astro-tigger-lsm version is less than 1.7.0... ===="
		install_type="fullstack"
	fi
else
	install_type="fullstack"
	echo "==== Installer fullstack mode - astro-tigger-lsm not found... ===="
fi	

# install astro-tigger-lsm
if [[ $install_type == "fullstack" ]]
then
	echo "==== Installing Tigger-LSM dependency from source... ===="
	sudo apt -y install git &&	
	cd /tmp &&
	rm -rf tigger-lsm
	git clone https://github.com/ska-sa/tigger-lsm.git &&
	cd tigger-lsm &&
	if [[ $distro_version == "18.04" ]]
	then
		sudo apt -y install libboost-python-dev casacore* 
	fi
	python3 setup.py install --user &&
	cd /tmp &&
	cd "${tigger_pwd}"
fi

echo "==== Installing package dependencies... ===="

# install Tigger deps
sudo apt -y install python3-pyqt5.qtsvg python3-pyqt5.qtopengl libqwt-qt5-6 &&

# compile PyQt-Qwt
if [[ $build_type == "source" ]]
then
    # install PyQt-Qwt deps
    sudo apt -y install pyqt5-dev pyqt5-dev-tools python3-pyqt5 libqwt-qt5-dev libqwt-headers libqt5opengl5-dev libqt5svg5-dev g++ dpkg-dev git &&
	if [[ $distro_version == "20.04" ]]
	then
		echo "==== Compiling PyQt-Qwt for $distro_name $distro_version... ===="
		cd /tmp &&
		rm -rf PyQt-Qwt
		git clone https://github.com/razman786/PyQt-Qwt.git &&
		cd PyQt-Qwt &&
		QT_SELECT=qt5 python3 configure.py --qwt-incdir=/usr/include/qwt --qwt-libdir=/usr/lib --qwt-lib=qwt-qt5 &&
		make -j4 &&
		sudo make install &&
		cd /tmp &&
		cd "${tigger_pwd}"

	elif [[ $distro_version == "18.04" ]]
	then
		echo "==== Compiling PyQt-Qwt for $distro_name $distro_version... ===="
		cd /tmp &&
		rm -rf PyQt-Qwt
		git clone https://github.com/razman786/PyQt-Qwt.git &&
		cd PyQt-Qwt &&
		git checkout ubuntu_18_04
        cp -a /usr/include/qwt header
        cp header/qwt*.h header/qwt/
		QT_SELECT=qt5 python3 configure.py --qwt-incdir=header/qwt --qwt-libdir=/usr/lib --qwt-lib=qwt-qt5 &&
		make -j4 &&
		sudo make install &&
		cd /tmp &&
		cd "${tigger_pwd}"
	else
		echo "==== Compiling PyQt-Qwt for $distro_name $distro_version... ===="
		cd /tmp &&
		rm -rf PyQt-Qwt
		git clone https://github.com/razman786/PyQt-Qwt.git &&
		cd PyQt-Qwt &&
		QT_SELECT=qt5 python3 configure.py --qwt-incdir=/usr/include/qwt --qwt-libdir=/usr/lib --qwt-lib=qwt-qt5 &&
		make -j4 &&
		sudo make install &&
		cd /tmp &&
		cd "${tigger_pwd}"
	fi
fi

# install PyQt-Qwt package
if [[ $build_type == "package" ]]
then
	if [[ $distro_version == "20.04" ]]
	then
		echo "==== Installing PyQwt for $distro_name $distro_version... ===="
		sudo dpkg -i ubuntu_20_04_deb_pkg/python3-pyqt5.qwt_2.00.00-1build1_amd64.deb
	elif [[ $distro_version == "18.04" ]]
	then
		echo "==== Installing PyQwt for $distro_name $distro_version... ===="
		sudo dpkg -i ubuntu_18_04_deb_pkg/python3-pyqt5.qwt_2.00.00_amd64.deb
	else
		echo "==== Error: No PyQt-Qwt package available for $distro_name $distro_version, please try: $0 --source ===="
		exit 1
	fi
fi

# Astropy =< 4.1 and scipy =< 1.5.2 are needed for Ubuntu 18.04 and Python 3.6
if [[ $distro_version == "18.04" ]]
then
    python_version=`python3 -c "import sys; print(''.join(map(str, sys.version_info[:2])))"`
    if [[ $python_version == "36" ]]
    then
        echo "==== Ubuntu 18.04 and Python 3.6 detected, adjusting package versions... ===="
        pip3 install astropy==4.1
        pip3 install scipy==1.5.2
    fi
fi

# install Tigger
python3 setup.py install --user

echo "==== Tigger installation complete! \o/ ===="
