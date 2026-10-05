"""
RETRY FAILED BATCHES
=====================

WHAT THIS PROGRAM DOES
------------------------
The main program (synthesize_rule_text.py) sometimes has to skip a
batch — for example, if the model's reply couldn't be read as JSON.
When that happens, every row in that batch gets its rule_text set to
None in output/rules_with_text.json, instead of a real sentence.

Re-running the whole main program from scratch just to fix a handful
of failed batches means waiting through every batch again, including
all the ones that already succeeded. This program is a faster
alternative: it opens the EXISTING output file, finds only the rows
still marked None, retries just those, and saves the same file again —
leaving every already-successful row completely untouched.

HOW THIS REUSES THE MAIN PROGRAM INSTEAD OF COPYING IT
----------------------------------------------------------
Rather than copying group_rows_by_table(), split_into_batches(),
build_prompt(), and ask_model() a second time into this file — which
would mean keeping two copies in sync forever — this program imports
synthesize_rule_text.py itself and calls its functions directly. If
you change a setting or fix something in synthesize_rule_text.py
later, this program automatically uses the updated version too, since
there is only ever one real copy of that logic.
"""

# ---------------------------------------------------------------------------
# SECTION 1: IMPORTS
# ---------------------------------------------------------------------------

import json
# Same as before: reading and writing the JSON file format.

import time
# Same as before: time.sleep() to pause between requests.

import os
# Same as before: reading the MOONSHOT_API_KEY environment variable.

from pathlib import Path
# Same as before: representing file locations.

import anthropic
# Same as before: talking to the API (Claude directly, or Kimi through
# Moonshot's Anthropic-compatible endpoint).

import synthesize_rule_text as main_program
# This line runs synthesize_rule_text.py's top-level code (its import
# statements and its SETTINGS section), and then gives us access to
# everything it defines — under the name main_program. So
# main_program.build_prompt(...) calls the exact same function defined
# in that file, and main_program.MODEL_PROVIDER reads the exact same
# setting. The "if __name__ == "__main__":" guard at the bottom of
# synthesize_rule_text.py means importing it this way does NOT run its
# main() function automatically — only calling main_program.main()
# ourselves would do that, and we never do.


# ---------------------------------------------------------------------------
# SECTION 2: SETTINGS
# ---------------------------------------------------------------------------

OUTPUT_FILE = Path("output/rules_with_text.json")
# The same file the main program writes to. We read it, fix what's
# missing, and save it back to this exact same location.


# ---------------------------------------------------------------------------
# SECTION 3: TALKING TO THE MODEL FOR ONE BATCH
# ---------------------------------------------------------------------------

def process_one_batch(rows_in_this_batch, client):
    """
    Send one batch of rows to the model, and either fill in each row's
    rule_text, or leave it as None if something still goes wrong. This
    mirrors the same three checks the main program performs, so a
    batch that fails here fails in exactly the same way it would in
    synthesize_rule_text.py.
    """

    prompt_text = main_program.build_prompt(rows_in_this_batch)
    reply_text = main_program.ask_model(prompt_text, client)

    if reply_text is None:
        print("  Still no answer text. Leaving these rows as None.")
        return rows_in_this_batch

    # Same code-fence-stripping as the main program: some replies come
    # back wrapped in a markdown ```json ... ``` block even when told
    # not to.
    cleaned_reply_text = reply_text.strip()
    if cleaned_reply_text.startswith("```"):
        first_newline_index = cleaned_reply_text.find("\n")
        if first_newline_index != -1:
            cleaned_reply_text = cleaned_reply_text[first_newline_index + 1:]
        if cleaned_reply_text.endswith("```"):
            cleaned_reply_text = cleaned_reply_text[:-3]
        cleaned_reply_text = cleaned_reply_text.strip()

    try:
        list_of_rule_texts = json.loads(cleaned_reply_text)
    except json.JSONDecodeError:
        print("  Still could not read the reply as JSON.")
        print("  Raw reply was:", reply_text[:500])
        return rows_in_this_batch

    if len(list_of_rule_texts) != len(rows_in_this_batch):
        print("  Still a mismatched number of answers. Leaving these rows as None.")
        return rows_in_this_batch

    for index_number in range(len(rows_in_this_batch)):
        rows_in_this_batch[index_number]["rule_text"] = list_of_rule_texts[index_number]

    return rows_in_this_batch


def wait_between_requests():
    """Pause the same amount of time the main program would, for whichever provider is active."""
    if main_program.MODEL_PROVIDER == "kimi":
        time.sleep(main_program.KIMI_REQUEST_DELAY_SECONDS)
    else:
        time.sleep(1)


# ---------------------------------------------------------------------------
# SECTION 4: THE MAIN PROGRAM
# ---------------------------------------------------------------------------

def main():

    with open(OUTPUT_FILE, "r", encoding="utf-8") as input_handle:
        all_rows = json.load(input_handle)

    # Split the rows we already have into two piles: the ones that
    # already worked, and the ones still needing a retry. We rebuild
    # the final file at the end from these two piles combined.
    rows_already_done = []
    rows_still_missing_text = []
    for one_row in all_rows:
        if one_row.get("rule_text") is None:
            rows_still_missing_text.append(one_row)
        else:
            rows_already_done.append(one_row)

    print("Rows already done:", len(rows_already_done))
    print("Rows needing a retry:", len(rows_still_missing_text))

    if len(rows_still_missing_text) == 0:
        print("Nothing to retry.")
        return

    # Re-use the main program's own grouping and batching logic, but
    # only on the rows that still need fixing.
    groups = main_program.group_rows_by_table(rows_still_missing_text)

    all_batches = []
    for group_key in groups:
        rows_in_this_group = groups[group_key]
        batches_for_this_group = main_program.split_into_batches(
            rows_in_this_group,
            main_program.MAX_ROWS_PER_REQUEST,
        )
        for one_batch in batches_for_this_group:
            all_batches.append((group_key, one_batch))

    # Build the same kind of client the main program would, for
    # whichever provider is currently set in synthesize_rule_text.py.
    if main_program.MODEL_PROVIDER == "kimi":
        client = anthropic.Anthropic(
            api_key=os.environ["MOONSHOT_API_KEY"],
            base_url="https://api.moonshot.ai/anthropic",
        )
    else:
        client = anthropic.Anthropic()

    total_number_of_batches = len(all_batches)
    batch_number = 0
    newly_processed_rows = []

    for group_key, rows_in_this_batch in all_batches:
        batch_number = batch_number + 1

        print(
            "Retrying batch "
            + str(batch_number)
            + " of "
            + str(total_number_of_batches)
            + ": "
            + str(group_key)
            + " ("
            + str(len(rows_in_this_batch))
            + " rows)"
        )

        finished_rows = process_one_batch(rows_in_this_batch, client)
        newly_processed_rows.extend(finished_rows)

        wait_between_requests()

    # Combine the rows that already worked with the rows we just
    # retried, and save the whole thing back to the same file.
    all_rows_final = rows_already_done + newly_processed_rows

    with open(OUTPUT_FILE, "w", encoding="utf-8") as output_handle:
        json.dump(all_rows_final, output_handle, indent=2)

    still_missing = 0
    for one_row in all_rows_final:
        if one_row.get("rule_text") is None:
            still_missing = still_missing + 1

    print("")
    print("Done. " + str(len(all_rows_final)) + " total rows saved.")
    print(str(still_missing) + " rows still missing rule_text after this retry.")


if __name__ == "__main__":
    main()
