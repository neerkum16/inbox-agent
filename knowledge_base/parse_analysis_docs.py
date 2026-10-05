"""
PARSE ANALYSIS DOCUMENTS
========================

WHAT THIS PROGRAM DOES
-----------------------
We have 8 Markdown (.md) files. Each one is a written analysis of one
COBOL banking transaction (things like "Create Account" or "Transfer
Funds"). Inside each file, some sections contain Markdown TABLES that
list business rules — for example, a table of validation checks, or a
table of "fail codes" (codes the old system uses to say why something
was rejected).

This program reads every .md file in the source_docs folder, finds
those two kinds of tables ("Validations" and "Fail Code Reference"),
and pulls every row out of them into a simple Python data structure.
It then saves everything it found into one combined file called
parsed_rules.json.

This program does NOT use any AI. It is a plain text-processing
program. We want the facts (fail codes, thresholds, exact wording) to
come through byte-for-byte correct, and ordinary string handling is
completely reliable for that job — there is no need for anything
smarter here.

WHAT A MARKDOWN TABLE LOOKS LIKE
---------------------------------
A table in a Markdown file looks like plain text, for example:

    | Fail Code | Meaning                        |
    |-----------|--------------------------------|
    | 1         | Account not found              |
    | 3         | Insufficient available funds   |

Line 1 is the HEADER ROW (the column names).
Line 2 is a SEPARATOR ROW made of dashes — it exists only to tell a
Markdown reader "yes, this really is a table". We do not want to keep
this line; we just use it as a signal that a real table follows.
Line 3 onward are DATA ROWS — the actual information we want.

WHAT A MARKDOWN HEADING LOOKS LIKE
------------------------------------
Markdown headings start with one or more "#" characters, followed by
a space, followed by the heading's text:

    # This is a top-level heading   (level 1)
    ## This is a sub-heading        (level 2)
    ### This is a smaller heading   (level 3)

The NUMBER of "#" characters tells you how "deep" the heading is
nested. We use this later to figure out where a section starts and
ends.
"""

# ---------------------------------------------------------------------------
# SECTION 1: IMPORTS
# ---------------------------------------------------------------------------
# "import" brings in code that already exists elsewhere, so we don't have
# to write it ourselves.

import json
# The "json" library lets Python save data to, and load data from, the
# JSON text format. JSON is a very common way of storing structured data
# (lists and key/value pairs) as plain text. We use json.dump() at the
# very end of this program to write our results out to a file.

from pathlib import Path
# "pathlib" is a built-in library for working with file and folder paths
# in a way that works correctly on both Windows and Mac/Linux. "Path" is
# a class (a blueprint for objects) that represents a location on disk.
# We only use two abilities of it here: building a folder path, and
# asking a folder "which files do you contain that match this pattern?"


# ---------------------------------------------------------------------------
# SECTION 2: SETTINGS
# ---------------------------------------------------------------------------
# These are just plain variables that describe where our input files live
# and where we want our output file to go. Keeping them at the top of the
# file, in capital letters, is a common Python convention for values that
# configure the program but never change while it runs.

SOURCE_FOLDER = Path("source_docs")
# This is the folder containing the 8 uploaded .md files.

OUTPUT_FOLDER = Path("output")
# This is the folder where we will write our results.

OUTPUT_FILE = OUTPUT_FOLDER / "parsed_rules.json"
# The "/" here is NOT division. Path objects override the "/" symbol so
# that combining two paths with "/" joins them into one path, the same
# way you'd join folder names with a slash when typing a file location.
# So this line means: "the file named parsed_rules.json, inside the
# output folder."


# ---------------------------------------------------------------------------
# SECTION 3: SMALL HELPER FUNCTION — READING ONE TABLE ROW
# ---------------------------------------------------------------------------

def split_table_row(row_text):
    """
    Take one line of a Markdown table, like:
        "| Fail Code | Meaning |"
    and return a plain Python list of the cell values, with the
    surrounding "|" characters and extra spaces removed:
        ["Fail Code", "Meaning"]
    """

    # .strip() removes any leading/trailing whitespace (spaces, tabs,
    # newline characters) from the very start and end of the text.
    trimmed_text = row_text.strip()

    # A Markdown table row usually starts and ends with "|". We remove
    # those two outer bars first, so that splitting on "|" afterwards
    # doesn't leave us with an empty first and last item.
    if trimmed_text.startswith("|"):
        trimmed_text = trimmed_text[1:]  # slicing: keep everything except character 0
    if trimmed_text.endswith("|"):
        trimmed_text = trimmed_text[:-1]  # keep everything except the very last character

    # .split("|") breaks the text into a list of pieces, cutting
    # wherever a "|" character appears. For example:
    #   " Fail Code | Meaning ".split("|")
    #   -> [" Fail Code ", " Meaning "]
    raw_cells = trimmed_text.split("|")

    # Each piece still has extra spaces around it, so we clean every
    # piece individually and build a new list of clean values.
    cleaned_cells = []
    for one_cell in raw_cells:
        cleaned_cells.append(one_cell.strip())

    return cleaned_cells


# ---------------------------------------------------------------------------
# SECTION 4: SMALL HELPER FUNCTION — RECOGNISING A HEADING LINE
# ---------------------------------------------------------------------------

def parse_heading(line_text):
    """
    Check whether a line of text is a Markdown heading.

    If it is, return two things:
        1. the heading LEVEL (a number: 1 for "#", 2 for "##", and so on)
        2. the heading TEXT (with the "#" characters and space removed)

    If it is NOT a heading, return (None, None) instead, so the calling
    code can easily check "did we get a real heading or not?"
    """

    if not line_text.startswith("#"):
        # If the line doesn't even start with "#", it definitely isn't
        # a heading, so we can stop immediately.
        return None, None

    # Count how many "#" characters are at the very start of the line.
    # We do this with a simple loop instead of anything clever, so it's
    # easy to follow: look at each character in turn, and as soon as we
    # find one that ISN'T "#", stop counting.
    hash_count = 0
    for one_character in line_text:
        if one_character == "#":
            hash_count = hash_count + 1
        else:
            break  # "break" immediately exits the loop early

    # After the "#" characters, a real heading has a space, then the
    # heading's text. line_text[hash_count:] means "everything in the
    # string starting from position hash_count onward".
    remainder = line_text[hash_count:]

    if not remainder.startswith(" "):
        # Something like "###NoSpace" is not a valid heading in
        # Markdown, so we treat it as "not a heading" to be safe.
        return None, None

    heading_text = remainder.strip()
    return hash_count, heading_text


# ---------------------------------------------------------------------------
# SECTION 5: THE MAIN PARSING LOGIC FOR ONE FILE
# ---------------------------------------------------------------------------
# This is the heart of the program. We read a file one line at a time,
# and keep track of "where we are" in the document as we go, using a
# small set of variables that we update as each line is read. This
# pattern — reading input step by step while remembering some state —
# is often called a "state machine", and it is a very common and simple
# way to process text.

def extract_rules_from_file(file_path):
    """
    Read one .md file and return a list of dictionaries, one dictionary
    per table row found inside a "Validations" or "Fail Code Reference"
    section anywhere in the document.
    """

    # This list will collect every row we find in this file. We return
    # it at the end of the function.
    all_rows_found = []

    # --- Variables that remember our position/context as we scan ---

    # While True, we are still in the introductory part of the document
    # (the title and the "> Transaction: ..." lines near the top), and
    # we're collecting that text as background information. We turn
    # this off once we reach the "Table of Contents" heading.
    still_in_document_header = True
    header_lines = []

    # current_section tells us whether we are currently inside a
    # "validations" section, a "fail_codes" section, or neither (None).
    current_section = None

    # current_section_level remembers HOW DEEP (heading level) the
    # section-starting heading was, e.g. if "### Validations" started
    # the section, this will be 3. We need this so that later, when we
    # see another heading, we can tell whether it's a sub-part of the
    # SAME section (a deeper heading) or the start of something new
    # (a heading at the same depth or shallower).
    current_section_level = None

    # current_subsection remembers the most recent smaller heading
    # inside our section, purely so we can label which specific table
    # a row came from (for example "DBCRFUN Fail Codes").
    current_subsection = None

    # table_buffer temporarily holds the raw lines of a table while
    # we're in the middle of reading it. Once the table ends (or the
    # file ends), we process everything in this list at once.
    table_buffer = []

    # -----------------------------------------------------------------
    # A small "inner function", defined here so it can see and update
    # the variables above without us having to pass them all around
    # as separate arguments every time.
    # -----------------------------------------------------------------
    def flush_table():
        """
        Take whatever is currently sitting in table_buffer, turn it
        into proper row dictionaries, add them to all_rows_found, and
        then empty table_buffer so we're ready for the next table.
        """

        # "nonlocal" tells Python that table_buffer here refers to the
        # variable from the surrounding function (extract_rules_from_file),
        # not a brand new local variable. We need this because we are
        # about to change table_buffer's contents, not just read them.
        nonlocal table_buffer

        # A real table needs at least 3 lines: the header row, the
        # dashes separator row, and at least one data row. If we have
        # fewer than that, there's nothing useful to extract.
        if len(table_buffer) >= 3:

            header_row_text = table_buffer[0]
            headers = split_table_row(header_row_text)

            # table_buffer[1] is the "|---|---|" separator row, which
            # we deliberately skip. table_buffer[2:] means "everything
            # from index 2 to the end of the list" — i.e. every data
            # row, skipping the header and the separator.
            data_row_lines = table_buffer[2:]

            for one_data_line in data_row_lines:
                cell_values = split_table_row(one_data_line)

                # If a row doesn't have the same number of cells as the
                # header row, something is malformed (perhaps a stray
                # "|" character inside a cell). Rather than guessing, we
                # skip that one row and move on, so one bad row doesn't
                # crash the whole program.
                if len(cell_values) != len(headers):
                    continue

                # Build a dictionary that pairs each header with its
                # matching value in this row, e.g.
                #   {"Fail Code": "1", "Meaning": "Account not found"}
                # We build it with an explicit loop and index numbers,
                # rather than a fancier one-line approach, so every
                # step is visible.
                row_dictionary = {}
                for index_number in range(len(headers)):
                    column_name = headers[index_number]
                    cell_value = cell_values[index_number]
                    row_dictionary[column_name] = cell_value

                # Now build the full record for this row, including
                # where it came from, and add it to our results list.
                all_rows_found.append({
                    "source_file": file_path.name,
                    "document_header": " | ".join(header_lines),
                    "section": current_section,
                    "subsection": current_subsection,
                    "table_data": row_dictionary,
                })

        # Whether or not we found a usable table, we clear the buffer
        # so the next table starts fresh. .clear() empties a list in
        # place, without creating a brand new list object.
        table_buffer.clear()

    # -----------------------------------------------------------------
    # Now we actually open the file and read it, one line at a time.
    # -----------------------------------------------------------------

    # "with open(...) as f:" opens the file and guarantees it gets
    # closed again automatically afterward, even if an error happens
    # partway through. encoding="utf-8" tells Python how to turn the
    # raw bytes on disk into text characters — utf-8 is the standard
    # choice and handles the special characters (like the "·" bullet
    # and curly quotes) that appear in these documents.
    with open(file_path, "r", encoding="utf-8") as f:

        # Looping "for raw_line in f" reads the file one line at a
        # time. Each raw_line still has an invisible newline character
        # at the end, which is why we call .strip() on it below.
        for raw_line in f:
            line = raw_line.strip()

            level, heading_text = parse_heading(line)

            # --- Step A: collect the document's introductory info ---
            if still_in_document_header:
                if level is not None and "Table of Contents" in heading_text:
                    # We've reached the Table of Contents heading, so
                    # the introductory part of the document is over.
                    still_in_document_header = False
                elif line.startswith(">"):
                    # Lines starting with ">" are Markdown "blockquotes".
                    # In these documents, the very first blockquote lines
                    # describe which transaction and which COBOL
                    # programs the document is about. We keep this text
                    # so it can be included later as helpful context.
                    # lstrip("> ") removes any leading "greater than"
                    # and space characters from the left side only.
                    header_lines.append(line.lstrip("> ").strip())

            # --- Step B: react to a heading line ---
            if level is not None:
                # Seeing ANY new heading means whatever table we might
                # have been reading has now ended, so save it.
                flush_table()

                if current_section is not None and level > current_section_level:
                    # This heading is MORE indented than the heading
                    # that started our current section, so it's a
                    # sub-part of the same section (for example,
                    # "### DBCRFUN Fail Codes" nested inside
                    # "## Fail Code Reference"). We stay inside the
                    # section, and just remember this as the current
                    # subsection label.
                    current_subsection = heading_text
                else:
                    # This heading is at the same depth or shallower
                    # than our section's starting heading, which means
                    # our current section (if any) has now ended.
                    # We then check: does this NEW heading itself start
                    # one of the two kinds of section we care about?
                    if "Validations" in heading_text:
                        current_section = "validations"
                        current_section_level = level
                        current_subsection = None
                    elif "Fail Code Reference" in heading_text:
                        current_section = "fail_codes"
                        current_section_level = level
                        current_subsection = None
                    else:
                        current_section = None
                        current_section_level = None
                        current_subsection = None

            # --- Step C: collect table lines while inside a section ---
            elif line.startswith("|"):
                if current_section is not None:
                    table_buffer.append(line)

            # --- Step D: anything else (blank line, ordinary text) ---
            else:
                if len(table_buffer) > 0:
                    # A non-table line has appeared right after some
                    # table lines, which means that table has ended.
                    flush_table()

        # The file has ended. If the very last thing in the file was
        # a table, we still need to flush it — nothing after it will
        # trigger that automatically.
        flush_table()

    return all_rows_found


# ---------------------------------------------------------------------------
# SECTION 6: THE MAIN PROGRAM
# ---------------------------------------------------------------------------
# This is the function that actually runs when you execute this script.
# It loops over every file, calls the function above on each one, and
# saves the combined results.

def main():

    # Make sure the output folder exists. parents=True means "create any
    # missing parent folders too", and exist_ok=True means "don't raise
    # an error if the folder is already there".
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    all_rules_from_every_file = []

    # SOURCE_FOLDER.glob("*.md") looks inside the source_docs folder and
    # returns every file whose name ends in ".md". "sorted()" puts them
    # in a predictable alphabetical order, so the program's output is
    # the same every time you run it.
    markdown_files = sorted(SOURCE_FOLDER.glob("*.md"))

    if len(markdown_files) == 0:
        print("No .md files found in the source_docs folder. Check the path.")
        return

    for one_file_path in markdown_files:
        rules_from_this_file = extract_rules_from_file(one_file_path)

        print(one_file_path.name + ": " + str(len(rules_from_this_file)) + " rows extracted")

        # .extend() adds every item from one list onto the end of
        # another list. (This is different from .append(), which would
        # add the WHOLE inner list as one single item instead of
        # adding its contents one by one.)
        all_rules_from_every_file.extend(rules_from_this_file)

    print("")
    print("Total rows extracted from all files: " + str(len(all_rules_from_every_file)))

    # Finally, save everything to the output JSON file.
    # "w" means "open for writing" (this will create the file, or
    # completely replace it if it already exists).
    # indent=2 tells json.dump to format the file with 2-space
    # indentation, so a human can open it and read it easily.
    with open(OUTPUT_FILE, "w", encoding="utf-8") as output_handle:
        json.dump(all_rules_from_every_file, output_handle, indent=2)

    print("Saved results to: " + str(OUTPUT_FILE))


# This last part is a standard Python convention. It means: "only run
# main() if this file is being run directly (like `python
# parse_analysis_docs.py`), not if it's being imported into some other
# program." It's not strictly needed for a small script like this one,
# but it's good habit to include.
if __name__ == "__main__":
    main()
