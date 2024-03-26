#!/usr/bin/env bash

while getopts ":p:c:fh" opt; do
    case $opt in
        p) policy_arg="$OPTARG";;
        c) config_arg="$OPTARG";;
        f) force=true;;
        h) echo "Usage: convert_policy_to_catalog.sh -c <config file> -p <policy file>"; exit 0;;
        \?) echo "Invalid option: -$OPTARG"; exit 1;;
    esac
done

# Get the absolute path of the input file
policy_file=$(cd "$(dirname $policy_arg)" && pwd)/$(basename "$policy_arg")

if [[ ! -f $policy_file ]] ; then
    echo "ERROR: $1 is not a valid file"
    echo "Usage: convert_policy_to_catalog.sh -c <config file> -p <policy file>"
    exit 1
fi

if [[ -z $config_arg ]]; then
    echo "No configuration file provided. Using default file (common.toml)"
    configuration_file=common.toml
else
    configuration_file=$config_arg
    echo "Configuration file provided: $configuration_file"
fi

# Setup some environment variables
export CONFIG_FILE=$configuration_file
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
    if [[ -f $PANDOC_DIR/$MD_FILE  ]]; then
        if [[ force == "true" ]]; then
            echo Markdown file exists, but force flag set. Recreating...
            $PANDOC_EXE "$POLICY_FILE" -o "$PANDOC_DIR/$MD_FILE" --wrap=none --to=gfm
        else
            echo Markdown file exists. Skipping conversion...
        fi
    else
        echo converting docx to md
        $PANDOC_EXE "$POLICY_FILE" -o "$PANDOC_DIR/$MD_FILE" --wrap=none --to=gfm
    fi

    echo Conversion to markdown completed...

    # Tokenize the document

    TOKENIZED_FILE=${POLICY_BASE/\.docx/\.tokenized}
    if [[ -f $PANDOC_DIR/$TOKENIZED_FILE ]]; then
        if [[ force == "true" ]]; then
            echo Tokenized file exists, but force flag set. Recreating...
            poetry run python -m pki_policy_tokenizer "$PANDOC_DIR/$MD_FILE"
        else
            echo Tokenized file exists. Skipping tokenization...
        fi
    else
        echo Tokenizing markdown file...
        poetry run python -m pki_policy_tokenizer "$PANDOC_DIR/$MD_FILE"
    fi

    echo tokenization completed

    OUTPUT_FILENAME=$(dirname $POLICY_FILE)/${POLICY_BASE/\.docx/_oscal\.json}

    # Convert the tokenized document to an OSCAL catalog
    if [[ -z $CONFIG_FILE ]]; then
        poetry run python -m oscal_pki_policy_converter "$PANDOC_DIR/$MD_FILE" > $OUTPUT_FILENAME
    else
        poetry run python -m oscal_pki_policy_converter --config $CONFIG_FILE "$PANDOC_DIR/$MD_FILE" > $OUTPUT_FILENAME
    fi
)