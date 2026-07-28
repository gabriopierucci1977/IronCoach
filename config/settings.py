"""
IronCoach - Settings

Gestisce la configurazione del progetto.
"""

import os
from dotenv import load_dotenv

# Carica le variabili dal file .env
load_dotenv()

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")