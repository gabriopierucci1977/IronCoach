#!/usr/bin/env sh
cd "$(dirname "$0")" || exit 1
if [ "$#" -ne 1 ] || [ -z "$1" ]; then
    echo "Uso: ./Avvia\\ revisione\\ coach.sh ID_ATLETA" >&2
    echo "ID_ATLETA è il record_id del profilo atleta Airtable." >&2
    exit 2
fi
exec python -c 'import sys; from backend.maintain_plan.coach_web import run; run(subject_ref=sys.argv[1])' "$1"
