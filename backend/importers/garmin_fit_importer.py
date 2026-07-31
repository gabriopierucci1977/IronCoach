"""
Garmin FIT Importer

Converte file Garmin FIT in IronCoachActivity.

Supporta:
- attività singole
- attività multisport Garmin
"""

import hashlib
from pathlib import Path

from fitparse import FitFile

from backend.models.activity import IronCoachActivity
from backend.models.activity_segment import IronCoachActivitySegment


class GarminFitImporter:
    """
    Importatore Garmin FIT.
    """

    def __init__(self, file_path: str):

        self.file_path = Path(file_path)


    def import_activity(self):

        if not self.file_path.exists():
            raise FileNotFoundError(
                f"FIT file not found: {self.file_path}"
            )


        fitfile = FitFile(
            str(self.file_path)
        )


        sessions = self._extract_sessions(
            fitfile
        )


        if len(sessions) > 1:
            return self._build_multisport_activity(
                sessions
            )


        return self._build_single_activity(
            sessions[0]
        )


    def _extract_sessions(self, fitfile):

        sessions = []

        for message in fitfile.get_messages(
            "session"
        ):

            data = {}

            for field in message:
                data[field.name] = field.value

            sessions.append(data)

        return sessions



    def _build_single_activity(self, data):

        return IronCoachActivity(

            activity_id=self.file_hash(),

            source="garmin",

            source_id=self.file_hash(),

            file_hash=self.file_hash(),

            start_time=str(
                data.get("start_time")
            ),

            sport=self._normalize_sport(
                data.get("sport")
            ),

            activity_type=str(
                data.get("sub_sport")
            ),

            duration_seconds=self._seconds(
                data.get("total_timer_time")
            ),

            distance_meters=data.get(
                "total_distance"
            ),

            avg_hr=data.get(
                "avg_heart_rate"
            ),

            max_hr=data.get(
                "max_heart_rate"
            ),

            avg_power=data.get(
                "avg_power"
            ),

            metadata={
                "garmin": {
                    "file_name": self.file_path.name,
                    "sub_sport": data.get(
                        "sub_sport"
                    )
                }
            }
        )



    def _build_multisport_activity(
        self,
        sessions
    ):

        segments = []


        for session in sessions:

            segment = IronCoachActivitySegment(

                sport=self._normalize_sport(
                    session.get("sport")
                ),

                activity_type=str(
                    session.get(
                        "sub_sport"
                    )
                ),

                start_time=str(
                    session.get(
                        "start_time"
                    )
                ),

                duration_seconds=self._seconds(
                    session.get(
                        "total_timer_time"
                    )
                ),

                distance_meters=session.get(
                    "total_distance"
                ),

                avg_hr=session.get(
                    "avg_heart_rate"
                ),

                max_hr=session.get(
                    "max_heart_rate"
                ),

                avg_power=session.get(
                    "avg_power"
                ),

                metadata={
                    "garmin": {
                        "original_sport":
                            session.get("sport")
                    }
                }
            )

            segments.append(segment)



        total_duration = sum(
            s.duration_seconds or 0
            for s in segments
        )


        total_distance = sum(
            s.distance_meters or 0
            for s in segments
        )


        return IronCoachActivity(

            activity_id=self.file_hash(),

            source="garmin",

            source_id=self.file_hash(),

            file_hash=self.file_hash(),

            sport="MULTISPORT",

            activity_type="triathlon",

            duration_seconds=total_duration,

            distance_meters=total_distance,

            segments=segments,

            metadata={
                "garmin": {
                    "file_name":
                        self.file_path.name,
                    "sessions":
                        len(segments)
                }
            }
        )



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

            "transition": "TRANSITION",

            "strength_training": "STRENGTH",
        }


        return mapping.get(
            str(value),
            str(value).upper()
            if value
            else None
        )