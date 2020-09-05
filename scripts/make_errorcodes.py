#!/usr/bin/env python3
"""Generate the errorcodes module starting from PostgreSQL documentation.

The script can be run at a new PostgreSQL release to refresh the module.
"""

# Copyright (C) 2010-2019 Daniele Varrazzo  <daniele.varrazzo@gmail.com>
# Copyright (C) 2020 The Psycopg Team
#
# psycopg2 is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# psycopg2 is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public
# License for more details.
from __future__ import print_function

import re
import sys
from urllib.request import urlopen
from collections import defaultdict


def main():
    if len(sys.argv) != 2:
        print("usage: %s /path/to/errorcodes.py" % sys.argv[0], file=sys.stderr)
        return 2

    filename = sys.argv[1]

    file_start = read_base_file(filename)
    # If you add a version to the list fix the docs (in errorcodes.rst)
    classes, errors = fetch_errors(
        ['9.1', '9.2', '9.3', '9.4', '9.5', '9.6', '10', '11', '12'])

    f = open(filename, "w")
    for line in file_start:
        print(line, file=f)
    for line in generate_module_data(classes, errors):
        print(line, file=f)


def read_base_file(filename):
    rv = []
    for line in open(filename):
        rv.append(line.rstrip("\n"))
        if line.startswith("# autogenerated"):
            return rv

    raise ValueError("can't find the separator. Is this the right file?")


def parse_errors_txt(url):
    classes = {}
    errors = defaultdict(dict)

    page = urlopen(url)
    for line in page:
        # Strip comments and skip blanks
        line = line.decode("ascii").split('#')[0].strip()
        if not line:
            continue

        # Parse a section
        m = re.match(r"Section: (Class (..) - .+)", line)
        if m:
            label, class_ = m.groups()
            classes[class_] = label
            continue

        # Parse an error
        m = re.match(r"(.....)\s+(?:E|W|S)\s+ERRCODE_(\S+)(?:\s+(\S+))?$", line)
        if m:
            errcode, macro, spec = m.groups()
            # skip errcodes without specs as they are not publically visible
            if not spec:
                continue
            errlabel = spec.upper()
            errors[class_][errcode] = errlabel
            continue

        # We don't expect anything else
        raise ValueError("unexpected line:\n%s" % line)

    return classes, errors


errors_txt_url = \
    "http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob_plain;" \
    "f=src/backend/utils/errcodes.txt;hb=%s"


def fetch_errors(versions):
    classes = {}
    errors = defaultdict(dict)

    for version in versions:
        print(version, file=sys.stderr)
        tver = tuple(map(int, version.split()[0].split('.')))
        tag = '%s%s_STABLE' % (
            (tver[0] >= 10 and 'REL_' or 'REL'),
            version.replace('.', '_'))
        c1, e1 = parse_errors_txt(errors_txt_url % tag)
        classes.update(c1)

        # This error was in old server versions but probably never used
        # https://github.com/postgres/postgres/commit/12f87b2c82
        errors['22']['22020'] = 'INVALID_LIMIT_VALUE'

        for c, cerrs in e1.items():
            errors[c].update(cerrs)

    return classes, errors


def generate_module_data(classes, errors):
    yield ""
    yield "# Error classes"
    for clscode, clslabel in sorted(classes.items()):
        err = clslabel.split(" - ")[1].split("(")[0] \
            .strip().replace(" ", "_").replace('/', "_").upper()
        yield "CLASS_%s = %r" % (err, clscode)

    for clscode, clslabel in sorted(classes.items()):
        yield ""
        yield "# %s" % clslabel

        for errcode, errlabel in sorted(errors[clscode].items()):
            yield "%s = %r" % (errlabel, errcode)


if __name__ == '__main__':
    sys.exit(main())
