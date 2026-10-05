"""
SHARED BANKDB HELPERS
=====================

This module contains the one customer-status lookup that Phase 2 drafting and
Phase 3 routing both need. Sharing it prevents the same SQL from slowly
diverging in two files. The helper only reads bankdb; it never changes data.
"""

# psycopg2 is the PostgreSQL driver used throughout this project. The extras
# module provides RealDictCursor, which returns rows with column names.
import psycopg2
import psycopg2.extras


def find_customers_by_email(connection, email_address):
    """Return every customer identity associated with an email address."""

    if email_address is None:
        return []

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT sort_code, customer_number
        FROM customer
        WHERE customer_email = %s;
        """,
        (email_address,),
    )
    rows = cursor.fetchall()
    cursor.close()

    return [dict(row) for row in rows]


def fetch_customer_status_details(connection, sort_code, customer_number):
    """Read the current status and reason for one known customer identity."""

    if sort_code is None or customer_number is None:
        return None

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT customer_status, status_reason
        FROM customer
        WHERE sort_code = %s
          AND customer_number = %s
        LIMIT 1;
        """,
        (sort_code, customer_number),
    )
    row = cursor.fetchone()
    cursor.close()

    if row is None:
        return None

    return dict(row)
