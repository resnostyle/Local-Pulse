import { useEffect, useState } from "react";

const EVENTS_BASE = (import.meta.env.VITE_EVENTS_BASE || "/events").replace(/\/$/, "");

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export default function App() {
  const [locations, setLocations] = useState([]);
  const [selected, setSelected] = useState(null);
  const [date, setDate] = useState(todayIso());
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${EVENTS_BASE}/index.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load locations (${r.status})`);
        return r.json();
      })
      .then((data) => {
        const locs = data.locations || [];
        setLocations(locs);
        if (locs.length > 0) setSelected(locs[0]);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    const { state, city } = selected;
    fetch(`${EVENTS_BASE}/locations/${state}/${city}/by-date/${date}.json`)
      .then((r) => {
        if (r.status === 404) return { date, events: [] };
        if (!r.ok) throw new Error(`Failed to load events (${r.status})`);
        return r.json();
      })
      .then((data) => setEvents(data.events || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selected, date]);

  if (error && locations.length === 0) {
    return (
      <div className="app">
        <h1>Local Pulse</h1>
        <p className="error">{error}</p>
        <p className="hint">
          Run the pipeline and serve <code>{EVENTS_BASE}/index.json</code> locally, or set{" "}
          <code>VITE_EVENTS_BASE</code> to your CDN URL.
        </p>
      </div>
    );
  }

  return (
    <div className="app">
      <header>
        <h1>Local Pulse</h1>
        <p className="tagline">Local events from static JSON</p>
      </header>

      <div className="controls">
        <label>
          Location
          <select
            value={selected ? `${selected.state}/${selected.city}` : ""}
            onChange={(e) => {
              const [state, city] = e.target.value.split("/");
              setSelected({ state, city });
            }}
          >
            {locations.map((loc) => (
              <option key={`${loc.state}/${loc.city}`} value={`${loc.state}/${loc.city}`}>
                {loc.city}, {loc.state}
              </option>
            ))}
          </select>
        </label>
        <label>
          Date
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
      </div>

      {loading && <p className="loading">Loading…</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && (
        <ul className="events">
          {events.length === 0 && <li className="empty">No events for this date.</li>}
          {events.map((ev) => (
            <li key={ev.id || ev.title}>
              <strong>{ev.title}</strong>
              {ev.venue && <span className="venue">{ev.venue}</span>}
              {ev.start_time && <time>{ev.start_time}</time>}
              {ev.source_url && (
                <a href={ev.source_url} target="_blank" rel="noreferrer">
                  Details
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
