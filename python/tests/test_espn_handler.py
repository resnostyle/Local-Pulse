"""Tests for ESPN handler."""

from datetime import datetime
from unittest.mock import patch

import pytest

from scraper.espn_handler import (
    _event_to_dict,
    _is_nc_event,
    fetch_espn_events,
)


class TestIsNcEvent:
    def test_venue_in_nc_state(self):
        config = {"state_code": "NC", "team_locations": []}
        event = {
            "competitions": [
                {
                    "venue": {"address": {"state": "NC"}},
                    "competitors": [],
                }
            ]
        }
        assert _is_nc_event(event, config) is True

    def test_team_location_matches(self):
        config = {"state_code": "NC", "team_locations": ["Charlotte", "Duke"]}
        event = {
            "competitions": [
                {
                    "venue": {},
                    "competitors": [
                        {"team": {"location": "Charlotte"}},
                    ],
                }
            ]
        }
        assert _is_nc_event(event, config) is True

    def test_no_match_returns_false(self):
        config = {"state_code": "NC", "team_locations": ["Charlotte"]}
        event = {
            "competitions": [
                {
                    "venue": {"address": {"state": "CA"}},
                    "competitors": [{"team": {"location": "LA"}}],
                }
            ]
        }
        assert _is_nc_event(event, config) is False

    def test_empty_competitions_returns_false(self):
        config = {"state_code": "NC", "team_locations": []}
        assert _is_nc_event({"competitions": []}, config) is False
        assert _is_nc_event({}, config) is False


class TestEventToDict:
    def test_converts_valid_event(self):
        event = {
            "id": "401234",
            "name": "Hornets vs Celtics",
            "date": "2026-03-20T19:00:00Z",
            "competitions": [
                {
                    "venue": {"fullName": "Spectrum Center", "address": {"city": "Charlotte"}},
                    "competitors": [],
                }
            ],
            "links": [{"rel": ["summary"], "href": "https://espn.com/game/401234"}],
            "status": {"type": {"description": "Scheduled"}},
        }
        result = _event_to_dict(event, "ESPN")
        assert result is not None
        assert result["title"] == "Hornets vs Celtics"
        assert result["start_time"] == datetime(2026, 3, 20, 19, 0, 0)
        assert result["venue"] == "Spectrum Center"
        assert result["city"] == "Charlotte"
        assert result["category"] == "Sports"
        assert result["source"] == "ESPN"
        assert "espn.com" in result["source_url"]

    def test_uses_start_date_fallback(self):
        event = {
            "name": "Game",
            "startDate": "2026-03-20T19:00:00Z",
            "competitions": [],
            "links": [],
            "status": {},
        }
        result = _event_to_dict(event, "ESPN")
        assert result is not None
        assert result["start_time"] == datetime(2026, 3, 20, 19, 0, 0)

    def test_returns_none_for_missing_name(self):
        event = {
            "date": "2026-03-20T19:00:00Z",
            "competitions": [],
            "links": [],
            "status": {},
        }
        assert _event_to_dict(event, "ESPN") is None

    def test_returns_none_for_missing_date(self):
        event = {
            "name": "Game",
            "competitions": [],
            "links": [],
            "status": {},
        }
        assert _event_to_dict(event, "ESPN") is None

    def test_builds_source_url_from_id_when_no_links(self):
        event = {
            "id": "401234",
            "name": "Game",
            "date": "2026-03-20T19:00:00Z",
            "competitions": [],
            "links": [],
            "status": {},
        }
        result = _event_to_dict(event, "ESPN")
        assert result is not None
        assert "401234" in result["source_url"]


class TestFetchEspnEvents:
    @patch("scraper.espn_handler._load_espn_config")
    def test_returns_empty_when_no_config(self, mock_load):
        mock_load.return_value = {}
        assert fetch_espn_events("ESPN") == []

    @patch("scraper.espn_handler._load_espn_config")
    def test_returns_empty_when_no_leagues_or_teams(self, mock_load):
        mock_load.return_value = {"state_code": "NC"}
        assert fetch_espn_events("ESPN") == []

    @patch("scraper.espn_handler.requests.get")
    @patch("scraper.espn_handler._load_espn_config")
    def test_fetches_and_filters_events(self, mock_load, mock_get):
        mock_load.return_value = {
            "state_code": "NC",
            "team_locations": ["Charlotte"],
            "leagues": [{"sport": "basketball", "league": "nba"}],
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "events": [
                {
                    "id": "401234",
                    "name": "Hornets vs Celtics",
                    "date": "2026-03-20T19:00:00Z",
                    "competitions": [
                        {
                            "venue": {
                                "fullName": "Spectrum Center",
                                "address": {"city": "Charlotte", "state": "NC"},
                            },
                            "competitors": [{"team": {"location": "Charlotte"}}],
                        }
                    ],
                    "links": [{"rel": ["summary"], "href": "https://espn.com/game/401234"}],
                    "status": {"type": {"description": "Scheduled"}},
                },
            ]
        }
        mock_get.return_value.raise_for_status = lambda: None

        events = fetch_espn_events("ESPN")
        assert len(events) == 1
        assert events[0]["title"] == "Hornets vs Celtics"

    @patch("scraper.espn_handler.requests.get")
    @patch("scraper.espn_handler._load_espn_config")
    def test_returns_empty_on_fetch_failure(self, mock_load, mock_get):
        import requests

        mock_load.return_value = {
            "leagues": [{"sport": "basketball", "league": "nba"}],
        }
        mock_get.side_effect = requests.RequestException("Connection failed")

        events = fetch_espn_events("ESPN")
        assert events == []

    @patch("scraper.espn_handler.requests.get")
    @patch("scraper.espn_handler._load_espn_config")
    def test_skips_non_nc_events(self, mock_load, mock_get):
        mock_load.return_value = {
            "state_code": "NC",
            "team_locations": ["Charlotte"],
            "leagues": [{"sport": "basketball", "league": "nba"}],
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "events": [
                {
                    "id": "401234",
                    "name": "Lakers vs Celtics",
                    "date": "2026-03-20T19:00:00Z",
                    "competitions": [
                        {
                            "venue": {"address": {"state": "CA"}},
                            "competitors": [{"team": {"location": "Los Angeles"}}],
                        }
                    ],
                    "links": [{"rel": ["summary"], "href": "https://espn.com/game/401234"}],
                    "status": {"type": {"description": "Scheduled"}},
                },
            ]
        }
        mock_get.return_value.raise_for_status = lambda: None

        events = fetch_espn_events("ESPN")
        assert len(events) == 0
