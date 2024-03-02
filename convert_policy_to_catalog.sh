#!/usr/bin/env bash

# Get the absolute path of the input file
policy_file=$(cd "$(dirname $1)" && pwd)/$(basename "$1")

if [[ ! -f $policy_file ]] ; then
    echo "ERROR: $1 is not a valid file"
    echo "usage: convert_policy_to_catalog.sh <policy file>"
    exit 1
fi


pandoc_dir=/tmp/.pandoc_install
pandoc_exe=$pandoc_dir/pandoc-3.1.11/bin/pandoc

if [[ ! -x $pandoc_exe ]]; then
    echo pandoc not found at $pandoc_dir. Installing from github

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
fi





# Convert the document to markdown with pandoc
output=${policy_file/\.docx/\.md}
echo converting $input to $output
# $pandoc_exe "$input" -o "$output" --wrap=none --to=gfm
# Setup the directory for installation of pandoc