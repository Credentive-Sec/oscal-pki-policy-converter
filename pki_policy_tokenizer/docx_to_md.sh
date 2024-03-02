#!/usr/bin/env bash
pandoc_dir=/tmp/.pandoc_install
pandoc_exe=$pandoc_dir/pandoc-3.1.11/bin/pandoc

if [[ ! -x $pandoc_exe ]]; then
    echo pandoc not found at expected location
    source install_pandoc.sh $pandoc_dir
fi

input=$1
output=${input/docx/md}
echo converting $input to $output
$pandoc_exe "$input" -o "$output" --wrap=none --to=gfm
