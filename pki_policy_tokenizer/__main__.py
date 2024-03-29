# Ignoring types here because stanza doesn't have type stubs
# type:ignore

import stanza
import pathlib
import argparse
import re

nlp = stanza.Pipeline(
    "en", download_method=stanza.DownloadMethod.REUSE_RESOURCES, processors="tokenize"
)


def get_sentences(input: str) -> list[str]:
    sentences: list[str] = []
    processed_text: stanza.Document = nlp(input)
    for sentence in processed_text.sentences:
        sentences.append(sentence.text)
    return sentences


def parse_document(policy_lines: list[str]) -> list[str]:
    line_count = len(policy_lines)

    # Precompile some regex we'll be using repeatedly
    # first, the regex for a markdown link
    md_link_re = re.compile(r"\[(?P<link>.*?)\]\((?P<target>.*?)\)(?P<text>.*)")

    processed_lines: list[str] = []
    for index, line in enumerate(policy_lines):
        # Check for blank lines (lines with only '\n') and just add them to the processed_lines list
        # Skip the rest of the processing for these lines
        if len(line) == 1:
            processed_lines.append("")
            continue

        # strip trailing newline from line
        if line[-1] == "\n":
            line = line[:-1]

        # Don't process section headers
        if line[0] == "#":
            processed_lines.append(line)

        # Don't process image links if they are on their own line
        elif line[0] == "!" and line[-1] in [")", "}"]:
            processed_lines.append(line)

        # Process lines starting with links "[" separately
        elif line[0] == "[":
            processed_lines.append(line)
            # **This code isn't quite ready yet** - Based on manual review, we can skip the links.
            # line_matches = md_link_re.match(line)
            # if line_matches is not None:
            #     first_line = ""
            #     matched_elements = line_matches.groupdict()
            #     if matched_elements["link"] != "":
            #         first_line += f"[{matched_elements['link']}]"
            #     if matched_elements["target"] != "":
            #         first_line += f"({matched_elements['target']})"
            #     if matched_elements["text"] != "":
            #         sentences = get_sentences(input=matched_elements["text"])
            #         first_line += sentences[0]
            #         processed_lines.append(first_line)
            #         # Add the rest of the sentences immediately after
            #         processed_lines.extend([sentence for sentence in sentences])
            # else:
            # This line starts with '[' but is not a link - just copy it like a regular line
            # processed_lines.extend(get_sentences(input=line))

        # if the line looks like a table
        elif line[0] == "|":
            # TODO: Implement html tables for this - Turns out there's nothing interesting in the tables. Just skipping
            processed_lines.append(line)
            # This doesn't quite work - need to implement as html table
            # split the line into columns
            # columns = line.split("|")
            # # for each column, split into sentences - reassemble with a sentance per line
            # # takes advantage of the fact that MD counts a single \n as equivalent to a space. * TODO: This doesn't work
            # for column in columns:
            #     sentences = get_sentences(input=column)
            #     # split strips the separater, so we'll need to add it back at the beginning of the first sentence
            #     if len(sentences) > 0:
            #         sentences[0] = "|" + sentences[0]
            #         processed_lines.extend(sentences)
            # # Add the terminating '|' a the end of the last column
            # processed_lines[-1] = processed_lines[-1] + "|"

        # Preserve empty lines - insert a blank string
        elif line[0] == "\n":
            processed_lines.append("")

        # If we get here, we're probably dealing with a regular line of text
        else:
            processed_lines.extend(get_sentences(input=line))

    return processed_lines


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser()

    arg_parser.add_argument("filename")

    args = arg_parser.parse_args()

    source_file = pathlib.Path(args.filename)

    output_file = source_file.with_suffix(".tokenized")

    # open and read the source file
    with open(source_file) as raw_doc:
        policy_lines = raw_doc.readlines()

    processed_lines = parse_document(policy_lines=policy_lines)

    # Write out the tokenized file, terminating each string with a newline
    output_file.write_text("\n".join(processed_lines), encoding="utf-8")
