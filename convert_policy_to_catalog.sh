#!/usr/bin/env bash

if [[ -z $1 ]] ; then
    echo "No catalog file name provided"
    echo "usage: convert_policy_to_catalog.sh <policy file>"
    exit 1
fi

# Get the absolute path of the input file
policy_file=$(cd "$(dirname $1)" && pwd)/$(basename "$1")

if [[ ! -f $policy_file ]] ; then
    echo "ERROR: $1 is not a valid file"
    echo "usage: convert_policy_to_catalog.sh <policy file>"
    exit 1
fi

# Setup some environment variables
export POLICY_FILE=$policy_file
export PANDOC_DIR=/tmp/.oscal-pki-policy-converter

# spawn a sub shell and change to the directory where the shell script exists
(
    cd "${0%/*}"
    if poetry env info --path 
    then
        echo Found virtual environment. 
    else
        echo No venv found. Creating venv and installing dependencies
        poetry install 
    fi

    # Check for the presence of pandoc and install it if it's not there
    PANDOC_EXE=$PANDOC_DIR/pandoc-3.1.11/bin/pandoc

    if [[ ! -x $PANDOC_EXE ]]; then
        echo pandoc not found at $pandoc_dir. Installing from github

        platform=`uname -i`

        if [ $platform="aarch64" ]; then
            filename=pandoc-3.1.11-linux-arm64.tar.gz
        elif [ $platform="x86_64" ]; then
            filename=pandoc-3.1.11-linux-amd64.tar.gz
        fi

        wget --directory-prefix=$PANDOC_DIR https://github.com/jgm/pandoc/releases/download/3.1.11/$filename

        (
            cd $PANDOC_DIR
            tar xzf $filename
        )
    fi

    echo pandoc installed, proceeding to conversion of docx to markdown

    # Convert the document to markdown with pandoc
    POLICY_BASE=$(basename $POLICY_FILE)
    MD_FILE=${POLICY_BASE/\.docx/\.md}
    echo converting $POLICY_FILE to $MD_FILE
    $PANDOC_EXE "$POLICY_FILE" -o "$PANDOC_DIR/$MD_FILE" --wrap=none --to=gfm

    echo conversion completed, tokenizing markdown file

    # Tokenize the document
     poetry run python -m pki_policy_tokenizer "$PANDOC_DIR/$MD_FILE"

    echo tokenization completed, converting to OSCAL catalog

    OUTPUT_FILENAME=$(dirname $POLICY_FILE)/${POLICY_BASE/\.docx/_oscal\.json}

    # Convert the tokenized document to an OSCAL catalog
    poetry run python -m oscal_pki_policy_converter "$PANDOC_DIR/$MD_FILE" > $OUTPUT_FILENAME
)