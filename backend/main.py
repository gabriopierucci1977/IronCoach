"""
IronCoach

Programma principale.
"""

from backend.airtable_client import AirtableClient


def main():

    client = AirtableClient()

    client.test_connection()


if __name__ == "__main__":
    main()