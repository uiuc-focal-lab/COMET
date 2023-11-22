#!/bin/bash
function get_sudo() {
    if ! sudo -S true < /dev/null 2> /dev/null; then
        echo "sudo access required for setting up comet:"
        sudo true
    fi
}

cur=$(pwd)

echo Thanks for using COMET. Your setup process will begin next...
get_sudo

# install dynamorio
sudo curl -sL https://github.com/DynamoRIO/dynamorio/releases/download/release_7_0_0_rc1/DynamoRIO-Linux-7.0.0-RC1.tar.gz | sudo tar xz -C /opt
# set up conda environment
# create conda environment
# ITHEMAL_HOME, DYNAMORIO_HOME are in the env file
conda env create -f scripts/environment.yml
# activate the conda environment
eval "$(conda shell.bash hook)"
conda activate comet
conda env config vars set COMET_HOME=$(pwd)
conda activate comet
./scripts/setup.sh

sudo chown -R root:root "${DYNAMORIO_HOME}"
sudo find "${DYNAMORIO_HOME}" -type d -exec chmod 755 {} \;
sudo find "${DYNAMORIO_HOME}" -type f -exec chmod 644 {} \;

BUILD_DIR="./models/Ithemal_gpu/data_collection/build"
if [ -d "${BUILD_DIR}" ]; then
    rm -rf "${BUILD_DIR}"
fi
./models/Ithemal_gpu/data_collection/build_dynamorio.sh
