#!/usr/bin/env bash

# Setup the directory for installation of pandoc
pandoc_dir=$1

platform=`uname -i`

if [ $platform="aarch64" ]; then
    filename=pandoc-3.1.11-linux-arm64.tar.gz
elif [ $platform="x86_64" ]; then
    filename=pandoc-3.1.11-linux-amd64.tar.gz
fi

wget --directory-prefix=$pandoc_dir https://github.com/jgm/pandoc/releases/download/3.1.11/$filename

(
    cd $pandoc_dir
    tar xzf $filename
)