"""
SYNTHESIZE RULE TEXT
====================

WHAT THIS PROGRAM DOES
-----------------------
The previous program (parse_analysis_docs.py) read our 8 documents and
saved every business-rule table row into output/parsed_rules.json. Each
row still looks very technical, for example:

    {"Fail Code": "1", "Condition": "Account not found (SQLCODE +100)"}

A customer-service reply can't use text like that directly — a real
customer doesn't know what "SQLCODE +100" means, and shouldn't need to.

THIS program reads that file, and for every row, asks the model (an AI
language model) to write ONE plain, friendly sentence that explains the
rule the way a human customer-service agent would say it. It then saves
everything — the original technical data PLUS the new plain-English
sentence — into a new file, output/rules_with_text.json.

WHY THIS NEEDS AN AI, WHEN THE FIRST PROGRAM DIDN'T
------------------------------------------------------
The first program's job was finding and copying exact facts out of a
table — something plain code does perfectly and reliably. THIS
program's job is writing NEW sentences in natural language, adapting
tone and wording to whatever the input happens to say. That's a task
language models are built for, and one plain code genuinely cannot do
well. This is why the project uses two separate programs instead of
one: each does the part it's actually good at.

HOW THE DATA FLOWS, STEP BY STEP
------------------------------------
1. We load parsed_rules.json into Python.
2. We GROUP related rows together (rows from the same table in the
   same document), so that instead of sending 381 separate requests to
   the model (slow, and likely to hit a rate limit), we send about 50
   requests, each covering a whole group of related rows at once.
3. For each group, we build a text PROMPT — an instruction plus the
   group's data — and send it to the model over the internet using
   Anthropic's official Python library.
4. The model sends back a text reply. We ask it to reply in JSON format
   specifically so that our program can read the reply back into a
   normal Python list, rather than having to guess how to split up a
   free-form paragraph.
5. We attach each new sentence back onto its matching original row.
6. Once every group is done, we save the complete, enriched list to
   output/rules_with_text.json.
"""

# ---------------------------------------------------------------------------
# SECTION 1: IMPORTS
# ---------------------------------------------------------------------------

import json
# Same "json" library as the previous program: lets us read and write
# the JSON text format, and also lets us turn a JSON-formatted string
# (like the model's reply) back into real Python lists/dictionaries.

import time
# A built-in library for anything related to time. We use time.sleep(),
# which pauses the program for a given number of seconds. We use this
# to wait briefly between requests, so we don't send them to Anthropic
# too quickly one after another.

from pathlib import Path
# Same as the previous program: represents file/folder locations in a
# way that works the same on Windows, Mac, and Linux.

import anthropic
# This is Anthropic's official Python library. We normally use it to
# talk to Claude, but as set up below, it also talks to Kimi, since
# Moonshot (the company behind Kimi) publishes an Anthropic-compatible
# endpoint.
# It is NOT part of standard Python — you install it yourself first,
# by running this command in your terminal:
#
#     pip install anthropic
#
# "pip" is Python's package installer: it downloads code that other
# people have written and published, so you don't have to write
# everything from scratch. Once installed, "import anthropic" makes
# all of that library's tools available to this program.

import os
# Built-in library for talking to the operating system. Used below to
# read the MOONSHOT_API_KEY environment variable when the toggle is
# set to "kimi".


# ---------------------------------------------------------------------------
# SECTION 2: SETTINGS
# ---------------------------------------------------------------------------

INPUT_FILE = Path("output/parsed_rules.json")
# The file written by the previous program — this program's input.

OUTPUT_FILE = Path("output/rules_with_text.json")
# Where this program will save its own results.

MODEL_PROVIDER = "kimi"
# Toggle: set this to "claude" to use Anthropic's Claude, 
#         set this to "kimi" to use Moonshot's Kimi model

if MODEL_PROVIDER == "kimi":
    MODEL_NAME = "kimi-k2.6"
else:
    MODEL_NAME = "claude-sonnet-5"
# Anthropic offers several different Claude models, which trade off
# speed, cost, and capability differently. This string tells the API
# exactly which model to use for every request in this program. 

MAX_ROWS_PER_REQUEST = 15
# The largest number of rows we will ever send to the model in a
# single request. Some of our groups (rows from the same table) are
# much bigger than others — one has 51 rows in it. A big group means a
# big prompt, and for a "thinking" model like Kimi, a big prompt can
# mean a LOT of reasoning text before it ever starts writing an answer.
# Rather than keep guessing at a bigger and bigger max_tokens value, we
# cap the request size itself: any group bigger than this gets split
# into several smaller requests instead of one large one.

# Moonshot's current API limit for this account is 3 requests per minute.
# Three requests per minute means requests must be spaced at least 20 seconds
# apart. We use 21 seconds to provide a small safety buffer and avoid hitting
# the limit because of timing differences between the local program and API.
# This delay is only needed for Kimi; Claude uses the existing request flow.
KIMI_REQUEST_DELAY_SECONDS = 21

# If the API still returns a temporary rate-limit error despite the delay,
# retry the exact same request instead of terminating the entire program.
# Limiting retries prevents an unexpected persistent API problem from causing
# the program to retry forever.
MAX_RATE_LIMIT_RETRIES = 5


# ---------------------------------------------------------------------------
# SECTION 3: GROUPING ROWS TOGETHER
# ---------------------------------------------------------------------------

def group_rows_by_table(all_rows):
    """
    Take the flat list of rows from parsed_rules.json, and organise it
    into groups, where every row in a group came from the same table in
    the same document.

    We do this because rows from the same table are related to each
    other (for example, all the fail codes for one COBOL program), so
    it makes sense to ask the model about them together in a single
    request, rather than one request per row.

    We return a Python DICTIONARY where:
      - each KEY identifies one group (which file, which section, which
        specific table within that section)
      - each VALUE is a list of the rows belonging to that group
    """

    groups = {}

    for one_row in all_rows:
        # A "tuple" is simply a small fixed group of values, written in
        # parentheses. We use one here as the dictionary key because a
        # single string couldn't easily represent "this exact file, in
        # this exact section, in this exact table" all at once — a
        # tuple of the three pieces of information does that naturally.
        group_key = (
            one_row["source_file"],
            one_row["section"],
            one_row["subsection"],
        )

        if group_key not in groups:
            # We haven't seen this exact group before, so start a new,
            # empty list for it.
            groups[group_key] = []

        groups[group_key].append(one_row)

    return groups


def split_into_batches(rows_in_one_group, max_batch_size):
    """
    Take one group's list of rows, and split it into several smaller
    lists, none bigger than max_batch_size. If the group is already
    small enough, this simply returns it as a single batch on its own.

    For example, a group of 51 rows with max_batch_size 15 becomes 4
    smaller batches: 15, 15, 15, and 6 rows.
    """

    all_batches = []

    # We step through the list max_batch_size rows at a time. start_index
    # marks where the next batch begins.
    start_index = 0
    while start_index < len(rows_in_one_group):
        end_index = start_index + max_batch_size

        # Python list slicing, rows_in_one_group[start_index:end_index],
        # takes everything from start_index up to (but not including)
        # end_index. If end_index runs past the end of the list, Python
        # simply stops at the last item instead of raising an error —
        # so we don't need to handle that case specially.
        one_batch = rows_in_one_group[start_index:end_index]
        all_batches.append(one_batch)

        start_index = end_index

    return all_batches


# ---------------------------------------------------------------------------
# SECTION 4: BUILDING THE TEXT WE SEND TO CLAUDE
# ---------------------------------------------------------------------------

def build_prompt(rows_in_this_group):
    """
    Build the instruction text (the "prompt") we will send to the model
    for one group of related rows. We build it up piece by piece as a
    list of lines, then join them into one big block of text at the
    end — this is easier to read and edit than one giant string.
    """

    prompt_lines = []

    prompt_lines.append(
        "You are helping build a customer-support knowledge base for a bank."
    )
    prompt_lines.append(
        "Below is a list of technical business rules, extracted from "
        "internal banking software documentation."
    )
    prompt_lines.append(
        "For EACH rule, write ONE short, clear sentence that a "
        "customer-service reply could use to explain the rule to a "
        "customer in plain English."
    )
    prompt_lines.append(
        "Do not mention COBOL, program names, fail codes, or any "
        "internal technical terms in your sentences."
    )
    prompt_lines.append("")
    prompt_lines.append(
        "Reply with ONLY a JSON array of strings — one string per rule, "
        "in the exact same order the rules are listed below. Do not "
        "include any explanation, headings, or text before or after "
        "the JSON array."
    )
    prompt_lines.append("")
    prompt_lines.append("Rules:")

    # We number each rule (1, 2, 3, ...) in the prompt itself. This
    # helps the model keep track of exactly how many answers are expected,
    # and helps us visually double-check the prompt while developing.
    for index_number in range(len(rows_in_this_group)):
        one_row = rows_in_this_group[index_number]

        # json.dumps() (note the "s" — this is the opposite direction
        # from json.dump()) converts a Python dictionary into a JSON
        # text string. We use it here just to neatly print the row's
        # technical data inside our prompt text.
        row_as_text = json.dumps(one_row["table_data"])

        prompt_lines.append(str(index_number + 1) + ". " + row_as_text)

    # "\n".join(prompt_lines) glues every item in the list together
    # into one string, placing a newline character between each item —
    # the same effect as if we had printed each line one after another.
    full_prompt_text = "\n".join(prompt_lines)

    return full_prompt_text


# ---------------------------------------------------------------------------
# SECTION 5: CALLING THE ANTHROPIC API
# ---------------------------------------------------------------------------

def ask_model(prompt_text, client):
    """
    Send one prompt to the model and return its reply as plain text.

    "client" is the object we use to actually talk to the API — we
    create one of these once, in main(), and pass it into this
    function each time, rather than creating a brand new connection
    for every single request.
    """

    # Kimi's "thinking" models reason step by step before answering,
    # which is valuable for genuinely hard problems, but this task
    # (rewording one technical rule into a plain sentence) isn't one of
    # them — and we've now confirmed Kimi can spend its ENTIRE
    # max_tokens budget reasoning about a batch of just 15 simple rows
    # without ever getting to the answer. Moonshot's API lets us turn
    # thinking off entirely for kimi-k2.6 with this parameter. We only
    # set it for the "kimi" branch — Claude isn't a thinking model in a
    # plain call like this one, so it doesn't need or accept this
    # parameter.
    extra_arguments = {}
    if MODEL_PROVIDER == "kimi":
        extra_arguments["thinking"] = {"type": "disabled"}

    # This is the actual network call. Behind the scenes, the anthropic
    # library packages up our request, sends it over the internet to
    # the API we configured above, waits for the model to generate a
    # reply, and hands that reply back to us as a Python object.
    # Moonshot limits this account to 3 requests per minute. Although the
    # main loop spaces Kimi requests apart, we also handle a 429 response here
    # so that a temporary timing-related rate-limit error does not terminate
    # the entire program. Claude keeps the same single-request behavior.
    rate_limit_attempt = 0

    while True:
        try:
            response = client.messages.create(
                model=MODEL_NAME,

                # max_tokens limits how long the model's reply is allowed to be.
                # A "token" is roughly a small chunk of a word. With thinking
                # turned off for Kimi, a batch of up to 15 short sentences
                # comfortably fits well within this.
                max_tokens=4000,

                # "messages" is a list representing the conversation. Here we
                # send a single message, playing the "user" role, containing
                # our whole prompt as its content.
                messages=[
                    {"role": "user", "content": prompt_text}
                ],

                # **extra_arguments "unpacks" the extra_arguments dictionary we
                # built above into individual keyword arguments here — so if
                # extra_arguments is {"thinking": {"type": "disabled"}}, this
                # line has the same effect as writing thinking={"type":
                # "disabled"} directly. We use this instead of writing it
                # directly because the Claude branch needs NO extra argument at
                # all, and this way the dictionary is simply empty for Claude
                # and unpacks into nothing.
                **extra_arguments,
            )
            break

        except anthropic.RateLimitError:
            # Only retry rate-limit errors for Kimi. Claude preserves the
            # original behavior and raises the API error immediately.
            if MODEL_PROVIDER != "kimi":
                raise

            rate_limit_attempt = rate_limit_attempt + 1

            # After the configured number of retries, re-raise the original
            # error rather than hiding a persistent API problem indefinitely.
            if rate_limit_attempt >= MAX_RATE_LIMIT_RETRIES:
                raise

            # Wait slightly longer than the normal request spacing before
            # retrying the exact same request.
            print(
                "  Rate limit reached. Waiting "
                + str(KIMI_REQUEST_DELAY_SECONDS + 4)
                + " seconds before retrying..."
            )
            time.sleep(KIMI_REQUEST_DELAY_SECONDS + 4)

    # The reply comes back as an object, not a plain string. The
    # model's reply text lives inside response.content — response.content is a
    # list (a reply COULD in principle contain several pieces). With
    # Claude, the text is normally the first piece. With Kimi, the
    # model "thinks" before answering, and that reasoning arrives as
    # its own block ahead of the actual answer — so instead of assuming
    # the text is always at position 0, we look through every block
    # and take the one whose type is "text". This works correctly for
    # both providers without needing to know in advance how many
    # blocks came back.
    reply_text = None
    for one_block in response.content:
        if one_block.type == "text":
            reply_text = one_block.text

    if reply_text is None:
        # Something went wrong badly enough that no "text" block ever
        # arrived. Rather than just returning None and leaving us to
        # guess why, print two things that explain what actually
        # happened: stop_reason tells us WHY the API stopped generating
        # (for example, "max_tokens" means it was cut off for running
        # out of room), and the list of block types tells us exactly
        # what WAS in the reply instead of a text block.
        print("  (diagnostic) stop_reason:", response.stop_reason)
        block_types_seen = []
        for one_block in response.content:
            block_types_seen.append(one_block.type)
        print("  (diagnostic) block types received:", block_types_seen)

    return reply_text


# ---------------------------------------------------------------------------
# SECTION 6: THE MAIN PROGRAM
# ---------------------------------------------------------------------------

def main():

    # Load the rows the previous program produced.
    with open(INPUT_FILE, "r", encoding="utf-8") as input_handle:
        all_rows = json.load(input_handle)

    groups = group_rows_by_table(all_rows)

    # Some groups are small enough to send in one request as-is. Others
    # are too big and need to be split into several smaller requests.
    # Here we go through every group once, split it if needed, and build
    # one flat list of "batches" to send — each batch remembers which
    # group it came from, purely so our progress messages stay readable.
    all_batches = []
    for group_key in groups:
        rows_in_this_group = groups[group_key]
        batches_for_this_group = split_into_batches(rows_in_this_group, MAX_ROWS_PER_REQUEST)
        for one_batch in batches_for_this_group:
            all_batches.append((group_key, one_batch))

    # Create ONE client object, which will be reused for every request
    # in this program. Which one we create depends on the MODEL_PROVIDER
    # toggle above.
    #
    # For "claude": creating anthropic.Anthropic() with no arguments
    # tells the library to look for your API key automatically, in an
    # environment variable named ANTHROPIC_API_KEY. This means your key
    # never has to appear anywhere in this file.
    #
    # On Windows PowerShell, you set that environment variable like this
    # before running this script:
    #
    #     $env:ANTHROPIC_API_KEY = "your-key-here"
    #
    # For "kimi": Moonshot (the company behind Kimi) publishes an
    # Anthropic-compatible endpoint, so we can keep using the same
    # anthropic library — we just point it at Moonshot's address
    # (base_url) and give it a Moonshot key instead, read from a
    # separate environment variable:
    #
    #     $env:MOONSHOT_API_KEY = "your-key-here"
    #
    if MODEL_PROVIDER == "kimi":
        client = anthropic.Anthropic(
            api_key=os.environ["MOONSHOT_API_KEY"],
            base_url="https://api.moonshot.ai/anthropic",
        )
    else:
        client = anthropic.Anthropic()

    # This list will end up holding every row from every group, each
    # one now with a new "rule_text" entry added to it.
    all_finished_rows = []

    total_number_of_batches = len(all_batches)
    batch_number = 0

    # Each item in all_batches is a pair: the group it came from, and
    # the (possibly smaller-than-the-full-group) list of rows in this
    # particular request.
    for group_key, rows_in_this_batch in all_batches:
        batch_number = batch_number + 1

        print(
            "Processing batch "
            + str(batch_number)
            + " of "
            + str(total_number_of_batches)
            + ": "
            + str(group_key)
            + " ("
            + str(len(rows_in_this_batch))
            + " rows)"
        )

        prompt_text = build_prompt(rows_in_this_batch)
        reply_text = ask_model(prompt_text, client)

        # ask_model() returns None if the reply never contained a "text"
        # block at all — for example, if a thinking model's reasoning
        # used up the whole max_tokens budget before it got to writing
        # an actual answer, cutting the reply off mid-thought. This is
        # a different problem from "the reply wasn't valid JSON", so we
        # check for it separately, with its own message, before we ever
        # try to parse anything.
        if reply_text is None:
            print("  The model did not return any answer text (its reply may have been cut off by max_tokens). Skipping this batch.")
            for one_row in rows_in_this_batch:
                one_row["rule_text"] = None
            all_finished_rows.extend(rows_in_this_batch)
            continue

        # Models sometimes wrap their JSON answer in a markdown code
        # fence (```json ... ```) even when told to reply with ONLY
        # JSON. Strip that off before parsing — this is a common
        # formatting quirk, not a real failure. If the reply doesn't
        # start with a fence, cleaned_reply_text just ends up identical
        # to reply_text and nothing changes.
        cleaned_reply_text = reply_text.strip()
        if cleaned_reply_text.startswith("```"):
            first_newline_index = cleaned_reply_text.find("\n")
            if first_newline_index != -1:
                cleaned_reply_text = cleaned_reply_text[first_newline_index + 1:]
            if cleaned_reply_text.endswith("```"):
                cleaned_reply_text = cleaned_reply_text[:-3]
            cleaned_reply_text = cleaned_reply_text.strip()

        # We asked the model to reply with ONLY a JSON array of strings.
        # json.loads() attempts to read that reply text as real JSON.
        # If the model's reply wasn't valid JSON for some reason (models
        # can occasionally add stray text despite instructions), this
        # will raise an error — which we catch here so one bad reply
        # doesn't stop the whole program.
        try:
            list_of_rule_texts = json.loads(cleaned_reply_text)
        except json.JSONDecodeError:
            print("  Could not read the model's reply as JSON. Skipping this batch.")
            # Print the actual reply so a repeat failure shows us real
            # evidence instead of just "it didn't work" a second time.
            print("  Raw reply was:", reply_text[:500])
            for one_row in rows_in_this_batch:
                one_row["rule_text"] = None
            all_finished_rows.extend(rows_in_this_batch)
            continue  # "continue" skips the rest of this loop step and moves to the next batch

        # We also asked for exactly one answer per rule. If the count
        # doesn't match, something went wrong, and we'd rather skip
        # this batch than risk matching answers to the wrong rows.
        if len(list_of_rule_texts) != len(rows_in_this_batch):
            print("  The model returned a different number of answers than expected. Skipping this batch.")
            for one_row in rows_in_this_batch:
                one_row["rule_text"] = None
            all_finished_rows.extend(rows_in_this_batch)
            continue

        # Attach each new sentence onto its matching row. We use a
        # plain index-number loop (rather than anything more compact)
        # so it's completely clear that answer number 1 goes with row
        # number 1, answer number 2 goes with row number 2, and so on.
        for index_number in range(len(rows_in_this_batch)):
            rows_in_this_batch[index_number]["rule_text"] = list_of_rule_texts[index_number]

        all_finished_rows.extend(rows_in_this_batch)

        # Moonshot limits this account to 3 requests per minute, so Kimi
        # requests must be spaced slightly more than 20 seconds apart.
        # Claude preserves the original one-second courtesy pause.
        if MODEL_PROVIDER == "kimi":
            time.sleep(KIMI_REQUEST_DELAY_SECONDS)
        else:
            time.sleep(1)

    # Save the final, enriched results.
    with open(OUTPUT_FILE, "w", encoding="utf-8") as output_handle:
        json.dump(all_finished_rows, output_handle, indent=2)

    print("")
    print("Done. Wrote " + str(len(all_finished_rows)) + " rows to " + str(OUTPUT_FILE))


if __name__ == "__main__":
    main()
