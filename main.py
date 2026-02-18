from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Dict, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from requests import Response

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

BASE_URL = "https://portales.uloyola.es/LoyolaHorario/horario.xhtml"

TITULACION = 403
CAMPUS = 2
TIPO = "G"
GRUPO = "A"


def get_academic_year() -> str:
    """Return academic year formatted as 2025%2F26 based on current date."""
    now = datetime.now()

    if now.month >= 9:  # September to December
        start_year = now.year
        end_year = now.year + 1
    else:  # January to August
        start_year = now.year - 1
        end_year = now.year

    short_end_year = str(end_year)[-2:]
    return f"{start_year}%2F{short_end_year}"


def build_url(ncurso: int) -> str:
    """Build Loyola schedule URL dynamically."""
    params = {
        "curso": get_academic_year(),
        "tipo": TIPO,
        "titu": TITULACION,
        "campus": CAMPUS,
        "ncurso": ncurso,
        "grupo": GRUPO,
    }

    return f"{BASE_URL}?{urlencode(params)}"


URL: str = (
    "https://portales.uloyola.es/LoyolaHorario/horario.xhtml"
    "?curso=2025%2F26&tipo=G&titu=403&campus=2&ncurso=1&grupo=A"
)

REQUEST_TIMEOUT: int = 15

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------------------------

@dataclass
class ScheduleEvent:
    title: str
    start: Optional[str]
    end: Optional[str]
    descripcion: str
    profesor: str
    obs: Any
    examen: Any


# ---------------------------------------------------------------------------
# NETWORK LAYER
# ---------------------------------------------------------------------------

def fetch_schedule_page(url: str) -> Response:
    """Fetch schedule HTML page."""
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        logger.error("Error fetching schedule page: %s", exc)
        raise


# ---------------------------------------------------------------------------
# PARSING LAYER
# ---------------------------------------------------------------------------

def extract_eventos_json(html: str) -> List[Dict[str, Any]]:
    """Extract eventos_calendario JSON array from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    script_tags = soup.find_all("script", type="text/javascript")

    for script in script_tags:
        content = script.string or ""
        if "function renderHorarioJs" in content:
            match = re.search(
                r"var eventos_calendario\s*=\s*(\[[\s\S]*?\]);",
                content,
            )
            if match:
                raw_json = match.group(1)
                try:
                    return json.loads(raw_json)
                except json.JSONDecodeError as exc:
                    logger.error("Invalid JSON format in eventos_calendario: %s", exc)
                    raise

    raise ValueError("Could not find eventos_calendario in page.")


# ---------------------------------------------------------------------------
# TRANSFORMATION LAYER
# ---------------------------------------------------------------------------

def map_to_schedule_events(data: List[Dict[str, Any]]) -> List[ScheduleEvent]:
    """Map raw JSON data to ScheduleEvent objects."""
    events: List[ScheduleEvent] = []

    for item in data:
        extended = item.get("extendedProps", {})

        events.append(
            ScheduleEvent(
                title=item.get("title", "No Title"),
                start=item.get("start"),
                end=item.get("end"),
                descripcion=extended.get("descripcion", "No description"),
                profesor=extended.get("profesor", "No professor"),
                obs=extended.get("obs", False),
                examen=extended.get("examen", False),
            )
        )

    return events


# ---------------------------------------------------------------------------
# ICS GENERATION
# ---------------------------------------------------------------------------

def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Safely parse ISO datetime string."""
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Invalid datetime format: %s", value)
        return None


def extract_location(title: str) -> str:
    """Extract location from title."""
    parts = title.split("Aula:")
    return parts[-1].strip() if len(parts) > 1 else "No Location"


def build_ics_calendar(events: List[ScheduleEvent]) -> Calendar:
    """Create Calendar object from schedule events."""
    calendar = Calendar()

    for item in events:
        event = Event()
        event.name = item.title

        start_dt = parse_datetime(item.start)
        end_dt = parse_datetime(item.end)

        if start_dt:
            event.begin = start_dt
        if end_dt:
            event.end = end_dt

        event.location = extract_location(item.title)

        event.description = (
            f"Description: {item.descripcion}\n"
            f"Professor: {item.profesor}\n"
            f"Observations: {item.obs}\n"
            f"Exam: {item.examen}"
        )

        calendar.events.add(event)

    return calendar


def save_calendar(calendar: Calendar, filepath: str) -> None:
    """Save calendar to file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(calendar)

    logger.info("ICS file successfully written to %s", filepath)


# ---------------------------------------------------------------------------
# APPLICATION ENTRY POINT
# ---------------------------------------------------------------------------

def main() -> None:
    for ncurso in range(1, 5):
        logger.info("Processing course %s", ncurso)

        url = build_url(ncurso)
        response = fetch_schedule_page(url)

        raw_events = extract_eventos_json(response.text)
        schedule_events = map_to_schedule_events(raw_events)

        calendar = build_ics_calendar(schedule_events)

        filename = f"calendario{ncurso}.ics" if ncurso > 1 else "calendario.ics"
        save_calendar(calendar, filename)

    logger.info("All calendars generated successfully.")



if __name__ == "__main__":
    main()
