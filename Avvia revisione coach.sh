#!/usr/bin/env sh
cd "$(dirname "$0")" || exit 1
if [ "$#" -gt 1 ]; then
    echo "Uso: ./Avvia\\ revisione\\ coach.sh [ID_ATLETA]" >&2
    exit 2
fi
if [ "$#" -eq 1 ]; then
    exec python -c 'import sys; from backend.maintain_plan.coach_web import run; run(subject_ref=sys.argv[1])' "$1"
fi
exec python -c 'from backend.maintain_plan.coach_web import run; run()'
