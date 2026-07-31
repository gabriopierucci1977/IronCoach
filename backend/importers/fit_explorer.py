"""
Garmin FIT Explorer

Primo strumento di analisi dei file FIT.
Non importa dati nel database.
Serve per capire la struttura reale dei file Garmin.
"""

import sys
from pathlib import Path

from fitparse import FitFile


def explore_fit(file_path: str):

    path = Path(file_path)

    if not path.exists():
        print(f"File non trovato: {path}")
        return

    print("=" * 60)
    print("GARMIN FIT EXPLORER")
    print("=" * 60)

    print(f"\nFile:")
    print(path.name)

    fitfile = FitFile(str(path))

    message_types = {}

    total_records = 0

    print("\nMessaggi Garmin trovati:")

    for record in fitfile.get_messages():

        name = record.name

        message_types[name] = (
            message_types.get(name, 0) + 1
        )

        if name == "record":
            total_records += 1


    for msg, count in sorted(message_types.items()):
        print(
            f"- {msg}: {count}"
        )

    print("\nRecord temporali:")
    print(total_records)

    print("\nCampi disponibili nei messaggi session:")

    fitfile = FitFile(str(path))

    for message in fitfile.get_messages("session"):

        for field in message:

            print(
                f"- {field.name}: {field.value}"
            )

        break


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Uso:"
        )

        print(
            "python -m backend.importers.fit_explorer FILE.fit"
        )

    else:

        explore_fit(sys.argv[1])