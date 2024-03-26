from __future__ import annotations
from oscal_pydantic import document, catalog
from oscal_pydantic.core import common
from datetime import datetime, timezone
import re
import uuid
from html.parser import HTMLParser
from typing import Any

from . import AbstractParser

class SimpleOscalParser(AbstractParser):
    # NOTE: This parser relies heavily on the specific format of the tokenized CP documents.
    def policy_to_catalog(self, parse_config: dict[str, Any], policy_text: list[str]) -> document.Document:
        # First, create an object variable representing the parser configuration toml file 
        if "parser-configuration" in parse_config.keys():
            self.parser_config: dict[str, Any] = parse_config["parser-configuration"]
        if "revision-table" in parse_config.keys():
            self.revision_table_headings: dict[str, Any] = parse_config["revision-table"]


        # We will parse the document and store all of the sections as their own list in a nested list
        section: list[str] = []
        sections: list[list[str]] = []

        # Parse the policy into lists
        for line in policy_text:
            if line: # Non-empty string is True
                if line[0] == "#":
                    # We've reached a new section. Assign the strings to the current
                    # section and reset the list
                    sections.append(section.copy())
                    section.clear()
                    section.append(line)
                else:
                    section.append(line)
            else:
                # Skip blank lines
                continue

        # We have now parsed the policy into a list of lists, where each
        # outer list represents a section of the document.

        # If the first list is the introduction/metadata, parse it now
        if self.parser_config["metadata_in_first_section"]:
            metadata = self.parse_metadata(sections[0])
            metadata.title = self.parser_config["title"]

        # Initialize an empty back-matter for later
        backmatter = None

        # We keep a stack to represent the current place in the TOC
        parent_stack: list[catalog.Group] = []

        # We also keep a list of ordered sections add to the final catalog
        section_groups: list[catalog.Group] = []

        # Step through the sections and generate the appropriate OSCAL objects.
        # We skip the first section because is it the title page and other stuff
        for section in sections[1:]:
            # Check for a couple of special sections that we expect to see: TOC and References
            # First line of section is the contents, so we can check there
            if "toc_marker" in self.parser_config.keys() and self.parser_config["toc_marker"] in section[0]:
                # In some versions of common, the TOC is a separate section - skip it.
                continue
            # If the config file specifies sections that will contain backmatter, and this section is one of them, parser it as such
            if "backmatter_sections" in self.parser_config.keys() and any([match for match in self.parser_config["backmatter_sections"] if match in section[0]]):
                # Pass everything except the title line to parse_backmatter
                backmatter = self.parse_backmatter(section[1:])
                continue
            
            # Assume every other section is a section with requirements
            # The first line has the section title, and because ift is MD,
            # the number of hashes indicate the depth in the TOC
            header_hashes = re.match(r"#+", section[0])
            if header_hashes is not None:
                section_depth = len(header_hashes.group(0))

                # Parse the section as a group
                current_group = self.section_to_group(
                    section_contents=section, section_depth=section_depth
                )

                if current_group is None:
                    # Sometimes we get blank headers in the Markdown. skip these.
                    continue
                # We use a stack to keep track of the heierarchy
                if section_depth == 1:
                    if parent_stack:
                        parent_stack[0] = current_group
                    else:
                        # e.g. this is the first run through the loop
                        parent_stack = [current_group]

                    # Add the top-level group to the final list of groups
                    section_groups.append(parent_stack[0])
                else:
                    # Careful! If we jump more than one level at a time, bad things could happen
                    if section_depth > len(parent_stack):
                        parent_stack.append(current_group)
                        # Add current group to the section above
                        self.add_subsection_to_parent(
                            parent_stack[section_depth - 2], current_group
                        )
                    elif section_depth == len(parent_stack):
                        # Replace the previous TOC leaf node with current
                        parent_stack[section_depth - 1] = current_group
                        self.add_subsection_to_parent(
                            parent_stack[section_depth - 2], current_group
                        )
                    elif section_depth < len(parent_stack):
                        # Trim the stack
                        parent_stack = parent_stack[:section_depth]
                        # Replace TOC leaf node with current
                        parent_stack[section_depth - 1] = current_group
                        self.add_subsection_to_parent(
                            parent_stack[section_depth - 2], current_group
                        )
            else:
                raise Exception("Section does not have a title")


        if not backmatter:
            # back-matter is required, so if we couldn't initialize it, we create an empty one now.
            backmatter = self.parse_backmatter([])

        common_catalog = catalog.Catalog(
            uuid=uuid.uuid4(),
            metadata=metadata,
            groups=section_groups,
            back_matter=backmatter,
        )

        return document.Document(catalog=common_catalog)

    # pandoc leaves some "span" tags in the document, so we need to strip html out of text
    def strip_html_from_text(self, input: str) -> str:
        return re.sub("<.*?>", "", input)
    
    # Sometimes we need to strip markdown out of a line to process it. This function strips out the most common MD tags
    def strip_markdown_from_text(self, input:str) -> str:
        input = input.replace("*", "") # Bold(**) and italic(*)
        input = input.replace("__", "") # Underline
        return input


    # utility function to determine whether a line of text has "requirement words" in it
    def is_requirement(self, input: str) -> bool:
        if any([keyword in input for keyword in self.parser_config["normative_keywords"]]):
            return True
        else:
            return False


    # Pass in a subsection and it's parent, return the parent with the child attached
    def add_subsection_to_parent(
        self, parent: catalog.Group, child: catalog.Group
    ) -> catalog.Group:
        if parent.groups:
            parent.groups.append(child)
        else:
            parent.groups = [child]

        return parent

    def section_to_group(
        self, section_contents: list[str], section_depth: int
    ) -> catalog.Group | None:
        # First line is the section header.
        # Strip off the leading hashes and the trailing space
        section_header = self.strip_html_from_text(re.sub("#+", "", section_contents[0]).strip())

        # Sometimes we get empty headings - if so we'll skip this whole process
        if not section_header:
            return None
        else:
            # Create a UUID to represent the group_id
            group_id = f"group-{uuid.uuid4()}"

            section_group = catalog.Group(
                id=group_id,
                title=f"{section_header}",
            )

            if len(section_contents) > 1:
                # Process contents to identify any text that contains requriements
                normative_statements: list[str] = []
                informative_statements: list[str] = []
                table_start = -1 # Track starting point of a table. Negative indicates we're not in a table at all
                contents_to_parse = section_contents[1:]
                for line_number, line in enumerate(contents_to_parse): # Skip the first line, it's the title.
                    if "<table" in line:
                        # We're inside an html table - skip until we reach the end (see next elif).
                        table_start = line_number
                        continue
                    elif "</table" in line:
                        # We're out of the table - send the table contents to the parse_html_table function
                        table_end = line_number
                        # table_contents = self.parse_html_table(
                        #     contents=section_contents[table_start:table_end+1], 
                        # )

                        # one_line_table = ""
                        # for row in table_contents:
                        #     one_line_table += "|" + "|".join(row) + "| <br/> "

                        one_line_table = " ".join(contents_to_parse[table_start:table_end+1])

                        if self.is_requirement(one_line_table):
                            normative_statements.append(one_line_table)
                        else:
                            informative_statements.append(one_line_table)
                        
                        table_start = -1
                    elif table_start > 0:
                        # If we're inside a table, keep going
                        continue
                    else:
                        # We're not in a table - process this as a regular line
                        if self.is_requirement(line):
                            normative_statements.append(self.strip_html_from_text(line))
                        else:
                            informative_statements.append(self.strip_html_from_text(line))

                # If a section has any requirements, they must go into an inner control group
                # If a section has no requriements, but some statements, they should be added as parts of the group
                # Finally, if a section has no text at all, just return the group.
                if normative_statements:
                    # The section contains requirements, and must have a control
                    # Controls must be inside an inner group since a group can't have both
                    # an inner group and inner controls
                    section_control_list: list[catalog.Control] = [
                        self.section_to_control(
                            section_title = section_header,
                            control_list=normative_statements,
                        )
                    ]

                    # Under some circumstances, 

                    section_control_group: catalog.Group = catalog.Group(
                        id=re.sub("group", "control", group_id),
                        title=f"{section_header}: Group for Normative Statements",
                    )
                    section_control_group.controls = section_control_list

                    section_group = self.add_subsection_to_parent(
                        section_group, section_control_group
                    )
                if informative_statements:
                    # add informative statements
                    informative_parts: list[catalog.BasePart] = []
                    for statement_number, overview_statement in enumerate(informative_statements):
                        informative_parts.append(
                            catalog.GroupPart(
                                id=f"{group_id}-{statement_number}",
                                name="overview",
                                prose=overview_statement,
                            )
                        )
                
                    section_group.parts = informative_parts

            return section_group


    def section_to_control(
        self, section_title: str, control_list: list[str]
    ) -> catalog.Control:
        # Strip off the leading hashes and the surrounding spaces
        control_title = f"{section_title}: Normative Statements"
        control_id = f"ctrl-{uuid.uuid4()}"
        control = catalog.Control(
            id=control_id,
            title=control_title,
            parts=[],
        )

        parts: list[catalog.BasePart] = []
        part_num = 1
        for section_line_text in control_list:
            # If we get here, it's a regular text line
            parts.append(
                catalog.StatementPart(
                    id=f"{re.sub("ctrl", "stmt", control_id)}-{part_num}",
                    name="statement",
                    prose=self.strip_html_from_text(section_line_text), # Strip any html left in.
                )
            )
            part_num += 1

        control.parts = parts

        return control


    def parse_metadata(self, introduction: list[str]) -> common.Metadata:
        version_marker: str = self.parser_config["version_marker"]
        publication_date_format: str = self.parser_config["publication_date_format"]
        version = ""
        published = None
        revisions = None
        table_start = -1
        in_toc: bool = False  # track if we're in a TOC
        for line_number, line in enumerate(introduction):
            if "<table" in line:
                # We're inside an html table - we should ignore all content until we are out again.
                table_start = line_number
            elif "</table" in line:
                table_end = line_number
                # Revision history is maintained in a table - parse it
                # Function works backwards from the END of a table, hence </table>
                revision_table = self.parse_html_table(introduction[table_start:table_end+1])
                revisions = self.revision_history_to_revisions(revision_table)

                # reset table_start counter
                table_start = -1
                
                # revision_history_to_revisions can return an empty list
                # In this case, set revisions to None so that it is excluded from
                # the final output
                if not revisions:
                    revisions = None
                    
                continue
            elif table_start > 0:
                continue

            # This TOC tracking code is very clumsy! TODO - fix it!
            elif "toc_marker" in self.parser_config and self.parser_config["toc_marker"] in line:
                in_toc = True
            elif line[0] == "[" and in_toc:
                continue
            elif version_marker in line and not in_toc:
                # Parse out the version number then move on
                # complicated pattern because of some strange inputs
                regex = f"^{version_marker}" + r"[\s\-\d]*\s"
                version = re.sub(regex, "", self.strip_markdown_from_text(line))
                continue
            # elif line[0] in "*<>[(" and not in_toc:
            #     # First character of the line indicates it's a structural or other
            #     # metadata line, ignore since we've already parsed the ones we're
            #     # interested in
            #     continue
            else:
                try:
                    # Try to parse the line as a date
                    published = datetime.strptime(self.strip_markdown_from_text(line), publication_date_format).replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    continue

        if not version or not published:
            raise ValueError("Introduction is missing Version and/or Publication Date.")
        else:
            return common.Metadata(
                title="Placeholder - will be replaced in calling function",
                published=published.isoformat(),
                version=version,
                oscal_version="1.1.2",  # TODO - get version from oscal-pydantic library
                revisions=revisions,
            )


    def parse_backmatter(self, contents: list[str]) -> common.BackMatter:
        # Parse the "References" in Appendix B and convert them to Resources in back-matter
        resource_table: list[list[str]] = []
        resource_list: list[common.Resource] = []

        # References are passed in as an html table - parse it
        for line_number, line in enumerate(contents):
            table_start = -1
            if "<table" in contents:
                # We're inside an html table - skip until we reach the end (see next elif).
                table_start = line_number
                continue
            elif "</table" in contents:
                # We're out of the table - send the table contents to the parse_html_table function
                table_end = line_number
                table_contents = self.parse_html_table(
                    contents=contents[table_start:table_end+1], 
                )
                # Do something with the contents
                # for row in table_contents:
                #     parts.append(
                #         catalog.StatementPart(
                #             id=f"{re.sub("ctrl", "stmt", control_id)}-{part_num}",
                #             name="statement",
                #             prose="|" + "|".join(row) + "|",
                #         )
                #     )
                #     part_num += 1
                table_start = -1
            elif table_start > 0:
                # If we're inside a table, keep going
                continue
            
            resource_table = self.parse_html_table(contents=contents) # Have to subtract 1 from index for the parse_html_table function
        
        resource_re = re.compile(r"^(?P<name>.*)\s*(?P<url>http.*)\s*$")
        # Format should be document_title, description, URL
        for resource in resource_table:
            resource_title = resource[0]
            resource_re_matches = resource_re.match(resource[1])
            if resource_re_matches is not None:
                match_dict = resource_re_matches.groupdict()
                resource_descripton = match_dict["name"]
                resource_url = match_dict["url"]
            else:
                # If we can't parse a resource - it's usually because it doesn't have a URL. 
                # OSCAL resources have to include a URL, so skip this one.
                continue

            resource_list.append(
                common.Resource(
                    uuid = uuid.uuid4(), # We are creating a new resource UUID every time - this should be re-considered
                    title=resource_title,
                    description=resource_descripton,
                    rlinks=[
                        common.ResourceLink(href=resource_url)
                    ],
                )
            )

        return common.BackMatter(resources=resource_list)


    def revision_history_to_revisions(self, revisions: list[list[str]]) -> list[common.Revision]:
        # Intialize empty revision list
        revision_list: list[common.Revision] = []

        # Get revision table column ids from config
        if "id_column" in self.revision_table_headings.keys():
            id_column = self.revision_table_headings["id_column"]
        if "date_column" in self.revision_table_headings.keys():
            date_column = self.revision_table_headings["date_column"]
        if "detail_column" in self.revision_table_headings.keys():
            detail_column = self.revision_table_headings["detail_column"]

        
        for row in revisions[1:]:
            version_id = row[id_column]
            try:
                published_date = (
                    datetime.strptime(row[date_column], "%B %d, %Y")
                    .replace(tzinfo=timezone.utc)
                    .isoformat()
                )
            except ValueError:
                # If we can't parse the date, we're probably in a weird header row
                continue
            revision_details = row[detail_column]
            revision_record = common.Revision(
                version=version_id,
                published=published_date,
                remarks=revision_details,
            )
            revision_list.append(revision_record)

        return revision_list


    def parse_html_table(self, contents: list[str]) -> list[list[str]]:
        # It's weird to define a class inside a function, but this is how HTMLParser works.
        class TableParser(HTMLParser):
            parsed_table: list[list[str]] = []
            current_row: list[str] = []
            current_cell: str
            in_row: bool = False
            in_cell: bool = False

            def handle_starttag(
                self, tag: str, attrs: list[tuple[str, str | None]]
            ) -> None:
                if tag == "tr":
                    # We're starting a new row
                    self.current_row = []
                    self.in_row = True
                if tag == "td":
                    self.current_cell = ""
                    self.in_cell = True

            def handle_endtag(self, tag: str) -> None:
                if tag == "tr":
                    self.parsed_table.append(self.current_row)
                    self.in_row = False
                if tag == "td":
                    self.current_row.append(self.current_cell)
                    self.in_cell = False
                else:
                    # There are some style tags in the rows - we want a space between the contents
                    if self.in_row and self.in_cell:
                        # Add a space to the cell we're processing now.
                        self.current_cell = self.current_cell + " "

            def handle_data(self, data: str) -> None:
                if self.in_row and self.in_cell:
                    self.current_cell = self.current_cell + data

            def return_results(self) -> list[list[str]]:
                return self.parsed_table

        table_parser = TableParser()
        table_parser.feed("".join(contents))
        return table_parser.return_results()
