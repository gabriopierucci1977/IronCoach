from __future__ import annotations

import json
import os
from copy import deepcopy

OVERRIDE_ENV = "IRONCOACH_MAINTAIN_PLAN_TRAINING_OVERRIDES"
ALLOWED_FIELDS = {
    "session_type",
    "intensity_method",
    "intensity_unit",
}


class RuntimeTrainingOverrideError(ValueError):
    pass


def apply_runtime_training_override(training):
    if type(training) is not dict:
        raise RuntimeTrainingOverrideError(
            "training must be an exact dict"
        )

    raw_config = os.getenv(OVERRIDE_ENV, "").strip()

    if not raw_config:
        return training

    try:
        config = json.loads(raw_config)
    except json.JSONDecodeError as error:
        raise RuntimeTrainingOverrideError(
            "override JSON non valido"
        ) from error

    if type(config) is not dict:
        raise RuntimeTrainingOverrideError(
            "override JSON deve essere un oggetto"
        )

    source_id = training.get("source_id")
    override = config.get(source_id)

    if override is None:
        return training

    if type(override) is not dict:
        raise RuntimeTrainingOverrideError(
            "override record non valido"
        )

    unsupported = set(override) - ALLOWED_FIELDS

    if unsupported:
        raise RuntimeTrainingOverrideError(
            "campi override non ammessi: "
            + ", ".join(sorted(unsupported))
        )

    result = deepcopy(training)
    result.update(deepcopy(override))

    raw = dict(result.get("raw") or {})
    raw["_runtime_training_override"] = {
        "record_id": source_id,
        "fields": sorted(override),
    }
    result["raw"] = raw

    return result
