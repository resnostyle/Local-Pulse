"""Local Pulse — data ingestion entry point (JSON file pipeline)."""

import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _filter_sources(sources: list[dict], only: list[str] | None) -> list[dict]:
    if not only:
        return sources
    only_set = {s.strip().lower() for s in only if s.strip()}
    return [
        src
        for src in sources
        if src.get("source", "").lower() in only_set
        or any(o in src.get("source", "").lower() for o in only_set)
    ]


def run_pipeline(only: list[str] | None = None, force: bool = False, reduce_after: bool = True) -> int:
    """Scrape due sources from calendars.yaml → raw JSON; optionally reduce to events/."""
    from pipeline.meta import is_source_due, load_source_meta
    from pipeline.reducer import reduce_all
    from pipeline.runner import scrape_one_source
    from pipeline.sources_yaml import load_sources_from_yaml

    sources = load_sources_from_yaml()
    sources = _filter_sources(sources, only or [])
    sources = [s for s in sources if s.get("enabled", True)]

    if not sources:
        logger.warning("No sources configured in calendars.yaml")
        return 0

    ran = 0
    for source in sources:
        name = source.get("source", "")
        meta = load_source_meta(name)
        if not is_source_due(source, meta, force=force):
            logger.info("Skipping %s (not due)", name)
            continue
        scrape_one_source(source)
        ran += 1

    logger.info("Scraped %d source(s)", ran)

    if reduce_after:
        counts = reduce_all()
        total = sum(counts.values())
        logger.info("Reduce complete: %d events across %d location(s)", total, len(counts))
        return total
    return ran


def cmd_reduce(state: str | None, city: str | None, all_locations: bool) -> int:
    from pipeline.reducer import reduce_all, reduce_location

    if all_locations or (not state and not city):
        counts = reduce_all()
        logger.info("Reduced %d location(s)", len(counts))
        return sum(counts.values())
    if not state or not city:
        raise SystemExit("Provide both --state and --city, or use --all")
    return reduce_location(state, city)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local Pulse ingestion — scrape sources and compile events JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py run                    # Scrape due sources + reduce
  python main.py run --force            # Scrape all sources, ignore intervals
  python main.py run --no-reduce        # Scrape only
  python main.py run --only "My Feed"
  python main.py reduce --all
  python main.py reduce --state nc --city raleigh
        """,
    )
    parser.add_argument(
        "command",
        choices=["run", "reduce"],
        help="run = scrape (+ reduce); reduce = compile raw/ to events/",
    )
    parser.add_argument("--only", action="append", metavar="SOURCE", help="Limit to named sources")
    parser.add_argument("--force", action="store_true", help="Ignore per-source scrape intervals")
    parser.add_argument("--no-reduce", action="store_true", help="Skip reduce after run")
    parser.add_argument("--all", action="store_true", dest="reduce_all", help="Reduce all locations")
    parser.add_argument("--state", metavar="STATE", help="State slug for single-location reduce")
    parser.add_argument("--city", metavar="CITY", help="City slug for single-location reduce")
    args = parser.parse_args()

    if args.command == "reduce":
        cmd_reduce(args.state, args.city, args.reduce_all or (not args.state and not args.city))
    else:
        run_pipeline(only=args.only, force=args.force, reduce_after=not args.no_reduce)


if __name__ == "__main__":
    main()
