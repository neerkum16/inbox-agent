"""
LOAD RULES INTO A VECTOR STORE
================================

WHAT THIS PROGRAM DOES
------------------------
The previous two programs (parse_analysis_docs.py and
synthesize_rule_text.py) produced output/rules_with_text.json — 380
plain-English business rules, each still stored as ordinary text.

Ordinary text can't be "searched by meaning". If the inbox agent later
receives a message asking "why was my transfer declined?", we need a
way to find the handful of rules that are actually relevant to that
question, out of 380 candidates — without the agent reading all 380
every single time.

This is what a VECTOR STORE is for. This program:

  1. Turns each rule's plain-English sentence into an EMBEDDING — a
     list of a few hundred numbers that represents the sentence's
     meaning. Sentences with similar meaning end up with similar
     numbers.
  2. Saves each rule, together with its embedding, into a Postgres
     table.

Later, a search step (not in this program) will turn a customer's
question into an embedding the same way, and ask Postgres for the
rules whose embeddings are numerically closest to it — which turns
out to be an effective way of finding rules that are actually about
the same topic, even if they don't share any of the same words.

WHY POSTGRES, AND WHAT "pgvector" IS
---------------------------------------
Postgres does not understand embeddings out of the box — a normal
Postgres column can hold a number, or text, but not "a list of 384
numbers, and please let me search by which rows are numerically
closest to another list of 384 numbers". pgvector is an official
Postgres EXTENSION (a plug-in) that adds exactly that: a new column
type called VECTOR, and the ability to sort rows by how close their
vector is to another one. Because it's "just" an extension to
Postgres, we keep using the exact same bankdb database, the same
psql tool, and the same login you already use for the CBSA data —
there is no second database system to run.

WHY EMBEDDINGS ARE COMPUTED ON YOUR OWN COMPUTER, NOT VIA AN API
--------------------------------------------------------------------
synthesize_rule_text.py needed Claude or Kimi because writing a new
sentence in fluent English is a genuinely hard task suited to a large
language model. Turning a sentence into an embedding is a much
smaller, well-defined task, and small models that run entirely on
your own computer do it well. We use one such model here — it costs
nothing per run, needs no API key, and needs no internet connection
once it's downloaded once.
"""

# ---------------------------------------------------------------------------
# SECTION 1: IMPORTS
# ---------------------------------------------------------------------------

import json
# Reading rules_with_text.json, and turning each rule's table_data
# dictionary into a JSON string for storage (Postgres can store JSON
# text directly, in a column type called JSONB).

import os
# Reading the database password from an environment variable, the same
# way earlier programs read API keys — so the password is never typed
# directly into this file.

from pathlib import Path
# Same as every earlier program: representing file locations.

import psycopg2
# The standard Python library for talking to a Postgres database. This
# is a different library from anthropic — Postgres and Claude/Kimi are
# two completely separate systems, so we need a separate tool for each.
# Not built in — install with: pip install psycopg2-binary

from pgvector.psycopg2 import register_vector
# A small helper from the pgvector project. On its own, psycopg2 has no
# idea what a "vector" column is — this one function teaches it how to
# convert a Python list of numbers into the format Postgres's vector
# type expects, and back again. We call it once, right after
# connecting. Not built in — install with: pip install pgvector

from sentence_transformers import SentenceTransformer
# The library that actually computes embeddings. It downloads a small
# pretrained model (the first time you run this program) and then runs
# entirely on your own computer from then on. Not built in — install
# with: pip install sentence-transformers
# (This also installs PyTorch, a much larger library that
# sentence-transformers uses internally to run the model. You don't
# need to use PyTorch directly yourself.)


# ---------------------------------------------------------------------------
# SECTION 2: SETTINGS
# ---------------------------------------------------------------------------

INPUT_FILE = Path("output/rules_with_text.json")
# The file produced by synthesize_rule_text.py.

DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
DATABASE_NAME = "bankdb"
DATABASE_USER = "postgres"
# Same connection details as your existing bankdb setup — this program
# adds a new table to that same database, rather than creating a
# second one.

DATABASE_PASSWORD = os.environ["PGPASSWORD"]
# Re-uses the exact same environment variable your setup_bankdb.ps1 /
# psql commands already rely on, so there's nothing new to configure.

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
# A small, well-established, general-purpose embedding model. It turns
# each sentence into a list of 384 numbers. There are larger embedding
# models that capture meaning slightly more precisely, but for 380
# short, plain-English sentences like ours, this size is a well-proven
# choice, and it runs quickly even without a graphics card.

EMBEDDING_DIMENSIONS = 384
# How many numbers make up one embedding from the model above. This
# has to exactly match when we create the database table below — the
# table's vector column is defined with this same number.

TABLE_NAME = "rule_knowledge_base"
# The new table this program creates (if it doesn't already exist) to
# hold the rules and their embeddings.


# ---------------------------------------------------------------------------
# SECTION 3: LOADING THE RULES FROM DISK
# ---------------------------------------------------------------------------

def load_rules_from_file():
    """Read rules_with_text.json and return it as a Python list of dictionaries."""

    with open(INPUT_FILE, "r", encoding="utf-8") as input_handle:
        rules = json.load(input_handle)

    return rules


# ---------------------------------------------------------------------------
# SECTION 4: CONNECTING TO THE DATABASE
# ---------------------------------------------------------------------------

def connect_to_database():
    """
    Open a connection to the bankdb Postgres database, enable pgvector
    on it, and teach that connection how to understand pgvector's
    vector type.
    """

    connection = psycopg2.connect(
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        dbname=DATABASE_NAME,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
    )

    # This has to run BEFORE register_vector() below. register_vector()
    # works by asking Postgres "what internal ID do you use for the
    # vector type?", so it can translate between that and Python lists
    # correctly — but if the vector type doesn't exist in this database
    # yet (because the extension was never turned on), there is no
    # answer for it to find, and register_vector() fails outright. This
    # only has any effect the very first time — if it's already
    # enabled, this line changes nothing.
    initial_cursor = connection.cursor()
    initial_cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    connection.commit()
    initial_cursor.close()

    # Without this line, psycopg2 would have no idea what to do with a
    # vector column — this teaches it, for this one connection.
    register_vector(connection)

    return connection


def ensure_table_exists(connection):
    """
    Make sure our table exists with the right columns. Safe to run
    every time this program runs — CREATE TABLE IF NOT EXISTS does
    nothing if the table already exists.
    """

    cursor = connection.cursor()

    # %s here is a placeholder that gets safely substituted by
    # psycopg2 — but table and column DEFINITIONS (unlike values you're
    # inserting) can't be parameterised that way, so we build this one
    # SQL string directly with an f-string instead. This is safe here
    # specifically because EMBEDDING_DIMENSIONS and TABLE_NAME are
    # fixed constants we wrote ourselves above, not values coming from
    # outside the program.
    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            rule_text     TEXT NOT NULL,
            embedding     VECTOR({EMBEDDING_DIMENSIONS}) NOT NULL,
            source_file   VARCHAR(100),
            section       VARCHAR(20),
            subsection    VARCHAR(200),
            table_data    JSONB,
            created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """
    cursor.execute(create_table_sql)

    connection.commit()
    cursor.close()


# ---------------------------------------------------------------------------
# SECTION 5: COMPUTING EMBEDDINGS
# ---------------------------------------------------------------------------

def compute_embeddings(rule_texts):
    """
    Turn a list of sentences into a list of embeddings (one embedding
    per sentence, in the same order).
    """

    print("Loading the embedding model (only slow the first time, while it downloads)...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    # .encode() accepts the WHOLE list of sentences at once, rather
    # than one at a time. It processes them together internally, which
    # is significantly faster than calling it 380 separate times would
    # be — this is the normal way this library is used, not a shortcut
    # specific to this program.
    print("Computing embeddings for", len(rule_texts), "rules...")
    embeddings = model.encode(rule_texts)

    return embeddings


# ---------------------------------------------------------------------------
# SECTION 6: SAVING EVERYTHING TO THE DATABASE
# ---------------------------------------------------------------------------

def save_rules_to_database(connection, rules, embeddings):
    """
    Replace the table's contents with the given rules and their
    embeddings.
    """

    cursor = connection.cursor()

    # We clear the table before inserting, so that running this
    # program again always leaves the table matching exactly what's
    # currently in rules_with_text.json — rather than piling up
    # duplicate rows from a previous run.
    cursor.execute(f"TRUNCATE TABLE {TABLE_NAME};")

    insert_sql = f"""
        INSERT INTO {TABLE_NAME}
            (rule_text, embedding, source_file, section, subsection, table_data)
        VALUES
            (%s, %s, %s, %s, %s, %s::jsonb)
    """
    # %s is a placeholder psycopg2 fills in safely for us, one per
    # value — this is the normal, safe way to insert data (as opposed
    # to building the SQL text yourself with the values pasted in,
    # which can break or even be dangerous if the text contains
    # unexpected characters). %s::jsonb tells Postgres to store that
    # particular value as a JSONB (structured JSON) column rather than
    # as plain text.

    for index_number in range(len(rules)):
        one_rule = rules[index_number]
        one_embedding = embeddings[index_number]

        # table_data is a Python dictionary in memory. json.dumps()
        # turns it into a JSON-formatted string, which is the form
        # Postgres's JSONB column expects to receive.
        table_data_as_json_text = json.dumps(one_rule["table_data"])

        # one_embedding arrives as a NumPy array (a fast, fixed-size
        # list of numbers used internally by the embedding model).
        # .tolist() converts it into an ordinary Python list, which is
        # the plain, well-understood form register_vector() knows how
        # to hand to Postgres's vector column.
        embedding_as_list = one_embedding.tolist()

        cursor.execute(
            insert_sql,
            (
                one_rule["rule_text"],
                embedding_as_list,
                one_rule["source_file"],
                one_rule["section"],
                one_rule["subsection"],
                table_data_as_json_text,
            ),
        )

    connection.commit()
    cursor.close()


# ---------------------------------------------------------------------------
# SECTION 7: THE MAIN PROGRAM
# ---------------------------------------------------------------------------

def main():

    rules = load_rules_from_file()
    print("Loaded", len(rules), "rules from", INPUT_FILE)

    # A row could still have rule_text set to None — for example, if
    # synthesize_rule_text.py never managed to fix every failed batch.
    # Rather than let the database insert crash on the first such row,
    # we filter those out here, and tell you clearly how many were
    # skipped, so nothing gets embedded silently missing its text.
    usable_rules = []
    skipped_count = 0
    for one_rule in rules:
        if one_rule.get("rule_text") is None:
            skipped_count = skipped_count + 1
        else:
            usable_rules.append(one_rule)

    if skipped_count > 0:
        print(skipped_count, "row(s) have no rule_text and will be skipped.")

    rules = usable_rules

    rule_texts = []
    for one_rule in rules:
        rule_texts.append(one_rule["rule_text"])

    embeddings = compute_embeddings(rule_texts)

    connection = connect_to_database()
    ensure_table_exists(connection)
    save_rules_to_database(connection, rules, embeddings)
    connection.close()

    print("")
    print("Done. Saved", len(rules), "rules with embeddings into the '" + TABLE_NAME + "' table.")


if __name__ == "__main__":
    main()
