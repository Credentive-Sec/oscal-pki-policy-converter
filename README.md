# oscal-pki-policy-converter
A tool to convert an RFC 3647 PKI Policy to an OSCAL Catalog 

# Requirements
This version has been tested on linux, and requires python 3.12 as well as [Poetry](https://python-poetry.org/).

Future versions will be installable without these requirements.

# Current limitations
This version of the software is heavily biased toward Federal Common Policy, and it is unclear how other versions of the PKI Policy will work. See ROADMAP below for plans to address this

# ROADMAP
The following items are on our short term roadmap:

- Abstract and parameterize the configuration of the parser, so that it is easier to adapt to different policies.
- Expand the output from a basic OSCAL catalog to a richer version that better supports the audit processes.
- Update the tool to simplify deployment and installation.