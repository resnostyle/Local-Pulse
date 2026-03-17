"""Fetch sports event data from scoreboard APIs (e.g. ESPN) and filter by configured region."""

import logging
from datetime import datetime
import requests
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_API_BASE = "https://site.api.espn.com/apis/site/v2/sports"
USER_AGENT = "Mozilla/5.0 (compatible; LocalPulse/1.0; +https://github.com/localpulse)"


def _load_espn_config() -> dict:
    """Load sports/ESPN config from espn.yaml."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "espn.yaml"
    if not config_path.exists():
        return {}
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.warning("ESPN config YAML parse error: %s", e)
        return {}
    if data is None or not isinstance(data, dict):
        return {}
    return data.get("espn", {})


def _is_nc_event(event: dict, config: dict) -> bool:
    """Return True if event involves NC teams or is in NC."""
    state_code = config.get("state_code", "NC")
    team_locations = set(loc.lower() for loc in config.get("team_locations", []))

    comps = event.get("competitions", [])
    if not comps:
        return False

    comp = comps[0]
    venue = comp.get("venue", {})
    addr = venue.get("address", {})
    if addr.get("state") == state_code:
        return True

    for c in comp.get("competitors", []):
        team = c.get("team", {})
        loc = (team.get("location") or "").strip()
        if loc and loc.lower() in team_locations:
            return True
    return False


def _event_to_dict(event: dict, source_name: str, config: dict) -> dict | None:
    """Convert sports API event to our event format."""
    try:
        date_str = event.get("date") or event.get("startDate", "")
        if not date_str:
            return None
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        start_time = dt.replace(tzinfo=None)

        name = event.get("name", "")
        if not name:
            return None

        comps = event.get("competitions", [])
        venue_name = None
        city = None
        if comps:
            v = comps[0].get("venue", {})
            venue_name = v.get("fullName")
            addr = v.get("address", {})
            city = addr.get("city")

        links = event.get("links", [])
        source_url = None
        for lnk in links:
            rels = lnk.get("rel") or []
            if any(r in ("summary", "live", "game", "boxscore") for r in rels):
                source_url = lnk.get("href")
                break
        if not source_url:
            eid = event.get("id", "")
            template = config.get("game_url_template", "https://www.espn.com/game/_/gameId/{id}")
            source_url = template.format(id=eid) if eid and "{id}" in template else (f"https://www.espn.com/game/_/gameId/{eid}" if eid else "")

        status = event.get("status", {})
        status_type = status.get("type", {})
        status_desc = status_type.get("description", "")

        return {
            "title": name,
            "description": status_desc or name,
            "start_time": start_time,
            "end_time": None,
            "venue": venue_name,
            "city": city,
            "category": "Sports",
            "source": source_name,
            "source_url": source_url,
            "recurring": False,
        }
    except (KeyError, ValueError) as e:
        logger.debug("Skip ESPN event %s: %s", event.get("id"), e)
        return None


def fetch_espn_events(source_name: str = "ESPN") -> list[dict]:
    """Fetch ESPN scoreboard for configured leagues, filter by state, return event dicts."""
    config = _load_espn_config()
    if not config:
        logger.warning("No ESPN config found at config/espn.yaml")
        return []

    leagues = config.get("leagues", [])
    team_locations = config.get("team_locations", [])
    if not leagues and not team_locations:
        logger.warning("ESPN config has no leagues or team_locations")
        return []

    all_events: list[dict] = []
    seen_ids: set[str] = set()

    for league_cfg in leagues:
        sport = league_cfg.get("sport", "")
        league = league_cfg.get("league", "")
        if not sport or not league:
            continue
        api_base = config.get("api_base_url", DEFAULT_API_BASE)
        url = f"{api_base.rstrip('/')}/{sport}/{league}/scoreboard"
        try:
            resp = requests.get(
                url,
                timeout=DEFAULT_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning("ESPN fetch %s failed: %s", url, e)
            continue
        except ValueError as e:
            logger.warning("ESPN parse %s failed: %s", url, e)
            continue

        events = data.get("events", [])
        for evt in events:
            if not _is_nc_event(evt, config):
                continue
            out = _event_to_dict(evt, source_name, config)
            if out is None:
                continue
            eid = evt.get("id", "")
            if eid and eid in seen_ids:
                continue
            if eid:
                seen_ids.add(eid)
            all_events.append(out)

    logger.info("Parsed %d NC sports events from ESPN", len(all_events))
    return all_events
