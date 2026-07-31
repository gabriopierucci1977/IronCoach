"""
Garmin FIT Importer

Converte file Garmin FIT in oggetti IronCoachActivity.
"""

import hashlib
from pathlib import Path

from fitparse import FitFile

from backend.models.activity import IronCoachActivity


class GarminFitImporter:
    """
    Importatore singolo file FIT Garmin.
    """

    def __init__(self, file_path: str):

        self.file_path = Path(file_path)


    def import_activity(self) -> IronCoachActivity:

        if not self.file_path.exists():
            raise FileNotFoundError(
                f"FIT file not found: {self.file_path}"
            )

        fitfile = FitFile(
            str(self.file_path)
        )

        session_data = self._extract_session(
            fitfile
        )

        sport = self._normalize_sport(
            session_data.get("sport")
        )

        metadata = {
            "garmin": {
                "file_name": self.file_path.name,
                "sub_sport": session_data.get(
                    "sub_sport"
                ),
                "trigger": session_data.get(
                    "trigger"
                ),
            }
        }


        return IronCoachActivity(

            activity_id=self.file_hash(),

            source="garmin",

            source_id=self.file_hash(),

            file_hash=self.file_hash(),

            start_time=str(
                session_data.get(
                    "start_time"
                )
            ),

            sport=sport,

            activity_type=str(
                session_data.get(
                    "sub_sport"
                )
            ),

            duration_seconds=self._seconds(
                session_data.get(
                    "total_timer_time"
                )
            ),

            distance_meters=session_data.get(
                "total_distance"
            ),

            elevation_gain=session_data.get(
                "total_ascent"
            ),

            elevation_loss=session_data.get(
                "total_descent"
            ),

            calories=session_data.get(
                "total_calories"
            ),

            avg_hr=session_data.get(
                "avg_heart_rate"
            ),

            max_hr=session_data.get(
                "max_heart_rate"
            ),

            avg_speed=session_data.get(
                "avg_speed"
            ),

            max_speed=session_data.get(
                "max_speed"
            ),

            avg_cadence=session_data.get(
                "avg_cadence"
            ),

            max_cadence=session_data.get(
                "max_cadence"
            ),

            avg_power=session_data.get(
                "avg_power"
            ),

            normalized_power=session_data.get(
                "normalized_power"
            ),

            training_load=session_data.get(
                "training_stress_score"
            ),

            training_effect=session_data.get(
                "total_training_effect"
            ),

            metadata=metadata
        )


    def _extract_session(self, fitfile):

        data = {}

        for message in fitfile.get_messages(
            "session"
        ):

            for field in message:

                data[field.name] = field.value

            break

        return data


    def file_hash(self):

        sha = hashlib.sha256()

        with open(
            self.file_path,
            "rb"
        ) as file:

            for chunk in iter(
                lambda: file.read(4096),
                b""
            ):

                sha.update(chunk)

        return sha.hexdigest()


    @staticmethod
    def _seconds(value):

        if value is None:
            return None

        return int(value)


    @staticmethod
    def _normalize_sport(value):

        mapping = {

            "running": "RUN",

            "cycling": "BIKE",

            "swimming": "SWIM",

            "strength_training": "STRENGTH",

        }

        return mapping.get(
            str(value),
            str(value).upper()
            if value
            else None
        )