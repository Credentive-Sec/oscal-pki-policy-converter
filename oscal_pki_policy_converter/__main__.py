from pathlib import Path, PurePath
import sys, os, argparse, tomllib
from typing import Any

from .  import parsers

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(
        prog="oscal_common_cp",
        description="A program to convert a parsed, tokenized RFC 3647 compliant PKI Policy to an OSCAL catalog.",
    )
    arg_parser.add_argument(
        "-c",
        "--config",
        dest="config_file",
        type=str,
        help="File containing parser configuration (default: common.toml)",
        default="common.toml",
    )
    arg_parser.add_argument(
        "-t",
        "--type",
        dest="parser_type",
        type=str,
        help="Type of parser to use (default: simple)",
        default="simple",
    )
    arg_parser.add_argument("filename", help="The filename of the policy to parse.")

    args = arg_parser.parse_args()

    if args.parser_type is not None:
        oscal_parser = parsers.choose_parser(args.parser_type)

    if args.config_file is not None:
        if PurePath(args.config_file).is_absolute():
            # If the user passes in a full path, use it
            config_file = Path(args.config_file)
        else:
            # Otherwise, assume that the config file is inside the package
            config_file = Path(os.getcwd(), Path(args.config_file))
    else:
        # If no config file is specified, assume we're processing common
        config_file = Path(sys.path[0], Path("common.toml"))


    # Parse TOML file into dictionary    
    parser_config: dict[str, Any] = {}
    try:
        parser_config=tomllib.load(open(config_file, "rb"))
    except tomllib.TOMLDecodeError as e:
        print(f"Could not parse provided config file as TOML: {config_file}")
        exit(1)

    policy_file_path = Path(args.filename)

    if policy_file_path.exists() and policy_file_path.is_file():
        with open(policy_file_path) as common_file:
            policy_catalog = oscal_parser.policy_to_catalog(
                parse_config=parser_config,
                policy_text=common_file.read().splitlines(),
            )
    else:
        print("You provided an argument that does not exist or is not a file.")
        arg_parser.print_help
        exit(1)

    if policy_catalog.catalog is not None:
        # Write the catalog to stdout
        title = policy_catalog.catalog.metadata.title
        version = policy_catalog.catalog.metadata.version
        oscal_version = policy_catalog.catalog.metadata.oscal_version
        # output_filename = (
        #     f"{title}-{version}-oscal-{oscal_version}-{args.parser_type}.json"
        # )
        # with open(
        #     file=Path.joinpath(Path.cwd(), "oscal-json", output_filename), mode="w"
        # ) as catalog_file:
        #     catalog_file.write(policy_catalog.model_dump_json())
        print(policy_catalog.model_dump_json())
    else:
        print("Could not parse catalog")
        exit(1)