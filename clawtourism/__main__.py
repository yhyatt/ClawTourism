"""CLI entry point for clawtourism."""
import sys


def main():
    if len(sys.argv) < 2:
        _print_help()
        sys.exit(0)

    cmd = sys.argv[1]

    # Flight subcommands
    if cmd in ("flight-status", "flight-monitor"):
        from clawtourism.flight_status_cli import main as flight_main
        flight_main(sys.argv[1:])
        return

    # Booking.com accommodation search
    if cmd == "accommodation":
        _accommodation_cmd(sys.argv[2:])
        return

    # Airbnb search via Apify
    if cmd == "airbnb":
        _airbnb_cmd(sys.argv[2:])
        return

    _print_help()
    sys.exit(1)


def _print_help():
    print("ClawTourism CLI")
    print("Commands:")
    print("  flight-status <FLIGHT>  [--date YYYY-MM-DD]")
    print("  flight-monitor <FLIGHT> --state-file <PATH>")
    print("  accommodation search --city CITY [--district D] --checkin YYYY-MM-DD --checkout YYYY-MM-DD")
    print("                       [--adults N] [--children-ages A A ...] [--min-rating F] [--top N]")
    print("  accommodation details --hotel-id ID --checkin YYYY-MM-DD --checkout YYYY-MM-DD")
    print("  airbnb search --location LOCATION --checkin YYYY-MM-DD --checkout YYYY-MM-DD")
    print("                [--adults N] [--children N] [--min-bedrooms N] [--top N]")


def _accommodation_cmd(args: list[str]):
    import argparse
    parser = argparse.ArgumentParser(prog="clawtourism accommodation")
    sub = parser.add_subparsers(dest="action")

    # search
    s = sub.add_parser("search")
    s.add_argument("--city", required=True)
    s.add_argument("--district", default=None)
    s.add_argument("--checkin", required=True)
    s.add_argument("--checkout", required=True)
    s.add_argument("--adults", type=int, default=2)
    s.add_argument("--children-ages", type=int, nargs="*", default=None)
    s.add_argument("--min-rating", type=float, default=8.5)
    s.add_argument("--top", type=int, default=5)
    s.add_argument("--no-reviews", action="store_true")

    # details
    d = sub.add_parser("details")
    d.add_argument("--hotel-id", type=int, required=True)
    d.add_argument("--checkin", required=True)
    d.add_argument("--checkout", required=True)
    d.add_argument("--adults", type=int, default=2)
    d.add_argument("--children-ages", type=int, nargs="*", default=None)

    ns = parser.parse_args(args)

    from clawtourism.accommodation import search_and_report, get_hotel_details, get_hotel_reviews

    if ns.action == "search":
        result = search_and_report(
            city=ns.city,
            checkin=ns.checkin,
            checkout=ns.checkout,
            adults=ns.adults,
            children_ages=ns.children_ages,
            district=ns.district,
            min_rating=ns.min_rating,
            top_n=ns.top,
            with_reviews=not ns.no_reviews,
        )
        print(result)

    elif ns.action == "details":
        import json
        details = get_hotel_details(ns.hotel_id, ns.checkin, ns.checkout, ns.adults, ns.children_ages)
        reviews = get_hotel_reviews(ns.hotel_id, limit=5)
        print(f"Name: {details.get('hotel_name')}")
        print(f"Address: {details.get('address')}, {details.get('city')}")
        print(f"Score: {details.get('review_score')} ({details.get('review_nr')} reviews)")
        print(f"Facilities: {[f.get('name') for f in details.get('facilities_block', {}).get('facilities', [])[:10]]}")
        print("\nTop reviews:")
        for r in reviews:
            print(f"  [{r['score']}] {r['title']}")
            if r['pros']: print(f"  + {r['pros'][:150]}")


def _airbnb_cmd(args: list[str]):
    import argparse
    parser = argparse.ArgumentParser(prog="clawtourism airbnb")
    sub = parser.add_subparsers(dest="action")

    s = sub.add_parser("search")
    s.add_argument("--location", required=True)
    s.add_argument("--checkin", required=True)
    s.add_argument("--checkout", required=True)
    s.add_argument("--adults", type=int, default=2)
    s.add_argument("--children", type=int, default=0)
    s.add_argument("--min-bedrooms", type=int, default=1)
    s.add_argument("--top", type=int, default=8)
    s.add_argument("--min-rating", type=float, default=4.5)

    ns = parser.parse_args(args)

    if ns.action == "search":
        from clawtourism.airbnb import search_and_report
        result = search_and_report(
            location=ns.location,
            checkin=ns.checkin,
            checkout=ns.checkout,
            adults=ns.adults,
            children=ns.children,
            min_bedrooms=ns.min_bedrooms,
            top_n=ns.top,
            min_rating=ns.min_rating,
        )
        print(result)


if __name__ == "__main__":
    main()
