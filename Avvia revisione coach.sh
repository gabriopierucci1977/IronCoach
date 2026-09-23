#!/usr/bin/env sh
cd "$(dirname "$0")" || exit 1
exec python -c 'from backend.maintain_plan.coach_web import run; run()'
