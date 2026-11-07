"""Usage:
    bikelake {list,extract,load,run} [source ...] [--force]
    bikelake stations [--every SECONDS]
"""

import argparse

from bikelake import stations
from bikelake.extract import extract
from bikelake.load import load
from bikelake.sources import SOURCES


def main() -> None:
    parser = argparse.ArgumentParser(prog="bikelake")
    parser.add_argument("command", choices=["list", "extract", "load", "run", "stations"])
    parser.add_argument("names", nargs="*", help="source names (default: all)")
    parser.add_argument("--force", action="store_true", help="re-download even if the file has landed")
    parser.add_argument("--every", type=int, help="stations: keep polling every N seconds")
    args = parser.parse_args()

    if args.command == "stations":
        stations.poll(args.every)
        return

    unknown = set(args.names) - SOURCES.keys()
    if unknown:
        parser.error(f"unknown source(s): {', '.join(sorted(unknown))}. Try: bikelake list")
    selected = [SOURCES[n] for n in args.names] if args.names else list(SOURCES.values())

    for source in selected:
        if args.command == "list":
            print(f"{source.name:28} {source.city:7} {len(source.resolve_urls()):>3} file(s)  {source.docs}")
        if args.command in ("extract", "run"):
            extract(source, force=args.force)
        if args.command in ("load", "run"):
            load(source)


if __name__ == "__main__":
    main()
