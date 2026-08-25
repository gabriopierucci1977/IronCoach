"""
IronCoach Decision Memory Viewer

Espone le decisioni memorizzate
in una forma consultabile.

Responsabilità:
- recuperare episodi recenti;
- restituire dati leggibili.

Non contiene:
- logica coaching;
- valutazione outcome;
- modifica memoria.
"""

from __future__ import annotations


class DecisionMemoryViewer:
    """
    Viewer della Decision Memory.
    """

    def __init__(
        self,
        repository,
    ):
        self.repository = repository

    def latest(
        self,
        limit=10,
    ):
        return self.repository.latest(
            limit=limit,
        )