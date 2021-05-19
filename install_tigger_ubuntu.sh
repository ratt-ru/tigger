#!/bin/bash

log_file=tigger_installer.log
error_file=tigger_installer.err

# custom redirection
exec 3>&1

# redirect stdout/stderr to a file
exec >$log_file 2> $error_file

# function echo to show echo output on terminal
echo() {
   # call actual echo command and redirect output to custom redirect
   command echo "$@" >&3
}

echo "==== Tigger v1.6.0 - Ubuntu install script ===="
echo "==== Log file: $log_file ===="
echo "==== Error log: $error_file ===="
printf "==== Tigger v1.6.0 - Ubuntu install script ====\n"

# install via packages by default
build_type="package"

# install only Tigger GUI by default
install_type="normal"

# store the location of this dir
tigger_pwd="${PWD}"

# exception handling
exception() {
	echo "==== Tigger installation script encountered an error ===="
	echo "==== Please check the log files $log_file and $error_file ===="
	echo "==== Ending Tigger installation script ¯\_(ツ)_/¯ ===="
	exit 1
	}

# display help
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
		distro_version=$(lsb_release -rs|sed -e 's/\.//g')
	else
		echo "==== Error: Ubuntu Linux not detected, stopping installation ===="
		printf "==== Error: Ubuntu Linux not detected, stopping installation ====\n"
		exit 1
	fi
else
	echo "==== Error: Unable to detect Linux distribution, stopping installation ===="
	printf "==== Error: Unable to detect Linux distribution, stopping installation ====\n"
	exit 1
fi

echo "==== Installer has detected Linux distribution as $distro_name $distro_version ===="
printf "==== Installer has detected Linux distribution as $distro_name $distro_version ====\n"

# check for pip3 and install if need be
if command -v pip3 > /dev/null 
then
	echo "==== Installer found pip3... ===="
	printf "==== Installer found pip3... ====\n"
else
	echo "==== Installer did not find pip3... ===="
	printf "==== Installer did not find pip3... ====\n"
	install_type="fullstack"
	sudo apt -y install python3-setuptools python3-pip 2>>$error_file || exception
fi

# check for astro-tigger-lsm
tigger_lsm=`pip3 list|grep astro-tigger-lsm|awk '{print $1}'`
if [[ $tigger_lsm == "astro-tigger-lsm" ]]
then
	echo "==== Installer found astro-tigger-lsm dependency... ===="
	printf "==== Installer found astro-tigger-lsm dependency... ====\n"
	tigger_lsm_version=`pip3 list|grep astro-tigger-lsm|awk '{print $2}'|sed -e 's/\.//g'`
	
	if [[ "$tigger_lsm_version" -lt "170" ]]
	then
		echo "==== Installer fullstack mode - astro-tigger-lsm version is less than 1.7.0... ===="
		printf "==== Installer fullstack mode - astro-tigger-lsm version is less than 1.7.0... ====\n"
		pip3 uninstall -y astro_tigger_lsm 2>>$error_file || exception
		install_type="fullstack"
	fi
else
	install_type="fullstack"
	echo "==== Installer fullstack mode - astro-tigger-lsm not found... ===="
	printf "==== Installer fullstack mode - astro-tigger-lsm not found... ====\n"
fi	

# install astro-tigger-lsm
if [[ $install_type == "fullstack" ]]
then
  if [[ $build_type == "source" ]] || [[ $distro_verison == "1804" ]]
  then
    echo "==== Installing Tigger-LSM dependency from source... ===="
    printf "==== Installing Tigger-LSM dependency from source... ====\n"
    sudo apt -y install git 2>>$error_file || exception
    cd /tmp || exception
    rm -rf tigger-lsm
    git clone https://github.com/ska-sa/tigger-lsm.git 1>>$log_file 2>>$error_file || exception
    cd tigger-lsm || exception

    if [[ $distro_version == "1804" ]]
    then
      sudo apt -y install libboost-python-dev casacore* 2>>$error_file || exception
      pip3 install -q astropy==4.1 || exception
      pip3 install -q scipy==1.5.2 || exception
    fi

    python3 setup.py install --user 1>>$log_file 2>>$error_file || exception
    cd /tmp || exception
    cd "${tigger_pwd}" || exception
  elif [[ $build_type == "package" ]]
  then
    echo "==== Installing Tigger-LSM dependency from pip3... ===="
    printf "==== Installing Tigger-LSM dependency from pip3... ====\n"
    pip3 install -q astro_tigger_lsm>=1.7.0 || exception
  fi
fi

echo "==== Installing package dependencies... ===="
printf "==== Installing package dependencies... ====\n"

# install Tigger deps
sudo apt -y install python3-pyqt5.qtsvg python3-pyqt5.qtopengl libqwt-qt5-6 2>>$error_file || exception

# compile PyQt-Qwt
if [[ $build_type == "source" ]]
then
    # install PyQt-Qwt deps
    sudo apt -y install pyqt5-dev pyqt5-dev-tools python3-pyqt5 libqwt-qt5-dev libqwt-headers libqt5opengl5-dev libqt5svg5-dev g++ dpkg-dev git 2>>$error_file || exception
	if [[ $distro_version == "2104" ]]
    then
		echo "==== Compiling PyQt-Qwt for $distro_name $distro_version... ===="
		printf "==== Compiling PyQt-Qwt for $distro_name $distro_version... ====\n"
        sudo apt -y install sip5-tools 2>>$error_file || exception
		cd /tmp || exception
		rm -rf PyQt-Qwt
		git clone https://github.com/razman786/PyQt-Qwt.git || exception
		cd PyQt-Qwt || exception
		QT_SELECT=qt5 python3 configure.py --qwt-incdir=/usr/include/qwt --qwt-libdir=/usr/lib --qwt-lib=qwt-qt5 || exception
		make -j4 || exception
		sudo make install || exception
		cd /tmp || exception
		cd "${tigger_pwd}" || exception
	elif [[ $distro_version == "2004" ]]
	then
		echo "==== Compiling PyQt-Qwt for $distro_name $distro_version... ===="
		printf "==== Compiling PyQt-Qwt for $distro_name $distro_version... ====\n"
		cd /tmp || exception
		rm -rf PyQt-Qwt
		git clone https://github.com/razman786/PyQt-Qwt.git || exception
		cd PyQt-Qwt || exception
		QT_SELECT=qt5 python3 configure.py --qwt-incdir=/usr/include/qwt --qwt-libdir=/usr/lib --qwt-lib=qwt-qt5 || exception
		make -j4 || exception
		sudo make install || exception
		cd /tmp || exception
		cd "${tigger_pwd}" || exception
	elif [[ $distro_version == "1804" ]]
	then
		echo "==== Compiling PyQt-Qwt for $distro_name $distro_version... ===="
		printf "==== Compiling PyQt-Qwt for $distro_name $distro_version... ====\n"
		cd /tmp || exception
		rm -rf PyQt-Qwt
		git clone https://github.com/razman786/PyQt-Qwt.git || exception
		cd PyQt-Qwt || exception
		git checkout ubuntu_18_04 || exception
		cp -a /usr/include/qwt header || exception
		cp header/qwt*.h header/qwt/ || exception
		QT_SELECT=qt5 python3 configure.py --qwt-incdir=header/qwt --qwt-libdir=/usr/lib --qwt-lib=qwt-qt5 || exception
		make -j4 || exception
		sudo make install || exception
		cd /tmp || exception
		cd "${tigger_pwd}" || exception
    else
		echo "==== Compiling PyQt-Qwt for $distro_name $distro_version... ===="
		printf "==== Compiling PyQt-Qwt for $distro_name $distro_version... ====\n"
		cd /tmp || exception
		rm -rf PyQt-Qwt
		git clone https://github.com/razman786/PyQt-Qwt.git || exception
		cd PyQt-Qwt || exception
		QT_SELECT=qt5 python3 configure.py --qwt-incdir=/usr/include/qwt --qwt-libdir=/usr/lib --qwt-lib=qwt-qt5 || exception
		make -j4 || exception
		sudo make install || exception
		cd /tmp || exception
		cd "${tigger_pwd}" || exception
	fi
fi

# install PyQt-Qwt package
if [[ $build_type == "package" ]]
then
	if [[ $distro_version == "2104" ]]
	then
		echo "==== Installing PyQwt for $distro_name $distro_version... ===="
		printf "==== Installing PyQwt for $distro_name $distro_version... ====\n"
		sudo dpkg -i ubuntu_21_04_deb_pkg/python3-pyqt5.qwt_2.00.00-1_amd64.deb || exception
	elif [[ $distro_version == "2004" ]]
	then
		echo "==== Installing PyQwt for $distro_name $distro_version... ===="
		printf "==== Installing PyQwt for $distro_name $distro_version... ====\n"
		sudo dpkg -i ubuntu_20_04_deb_pkg/python3-pyqt5.qwt_2.00.00-1build1_amd64.deb || exception
	elif [[ $distro_version == "1804" ]]
	then
		echo "==== Installing PyQwt for $distro_name $distro_version... ===="
		printf "==== Installing PyQwt for $distro_name $distro_version... ====\n"
		sudo dpkg -i ubuntu_18_04_deb_pkg/python3-pyqt5.qwt_2.00.00_amd64.deb || exception
	else
		echo "==== Error: No PyQt-Qwt package available for $distro_name $distro_version, please try: $0 --source ===="
		printf "==== Error: No PyQt-Qwt package available for $distro_name $distro_version, please try: $0 --source ====\n"
		exit 1
	fi
fi

# Astropy =< 4.1 and scipy =< 1.5.2 are needed for Tigger on Ubuntu 18.04 and Python 3.6
if [[ $distro_version == "1804" ]]
then
    # check if Python 3.6 in use
    python_version=`python3 -c "import sys; print(''.join(map(str, sys.version_info[:2])))"`
    if [[ $python_version == "36" ]]
    then
		echo "==== Ubuntu 18.04 and Python 3.6 detected, adjusting package versions... ===="
		printf "==== Ubuntu 18.04 and Python 3.6 detected, adjusting package versions... ====\n"

		# check if Astropy version is already 4.1
		astropy_verison=`pip3 list|grep astropy|awk '{print $2}'|sed -e 's/\.//g'`
		if [[ "$astropy_version" -ne "41" ]]
		then
			pip3 uninstall -y astropy || exception
			pip3 install -q astropy==4.1 || exception
		fi

		# check if scipy version is already 1.5.2
		scipy_verison=`pip3 list|grep scipy|awk '{print $2}'|sed -e 's/\.//g'`
		if [[ "$scipy_version" -ne "152" ]]
		then
			pip3 uninstall -y scipy || exception
			pip3 install -q scipy==1.5.2 || exception
		fi
    fi
fi

# install Tigger
python3 setup.py install --user 1>>$log_file 2>>$error_file && echo "==== Tigger installation complete! \o/ ====" || exception