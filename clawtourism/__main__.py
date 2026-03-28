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

    # Google Places
    if cmd == "places":
        _places_cmd(sys.argv[2:])
        return

    # Flight search (prices/availability)
    if cmd == "flights":
        _flights_cmd(sys.argv[2:])
        return

    # Currency exchange rates
    if cmd == "currency":
        from clawtourism.currency import main as currency_main
        currency_main(sys.argv[2:])
        return

    # Destination intelligence (country facts + travel guide)
    if cmd == "destination":
        from clawtourism.destination import main as destination_main
        destination_main(sys.argv[2:])
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
    print("  places restaurants --location CITY/NEIGHBORHOOD [--radius M] [--top N]")
    print("  places attractions --location CITY [--radius M] [--family] [--top N]")
    print("  places search --location CITY --type PLACE_TYPE [--top N]")
    print("  flights search --from OTP --to VIE --date 2026-04-03 [--adults N] [--children N] [--direct]")
    print("                 (city names also accepted: --from bucharest --to vienna)")
    print("  currency convert <amount> <FROM> <TO[,TO2,...]>")
    print("  currency rates <BASE>")
    print("  currency historical <YYYY-MM-DD> <FROM> <TO[,TO2,...]>")
    print("  destination info <destination> [--country <country>]")
    print("  destination country <country>")
    print("  destination guide <destination>")


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


def _places_cmd(args: list[str]):
    import argparse
    parser = argparse.ArgumentParser(prog="clawtourism places")
    sub = parser.add_subparsers(dest="action")

    for action in ("restaurants", "attractions", "search"):
        s = sub.add_parser(action)
        s.add_argument("--location", "--city", required=True, dest="location")
        s.add_argument("--radius", type=int, default=1500)
        s.add_argument("--min-rating", type=float, default=4.3)
        s.add_argument("--top", type=int, default=8)
        if action == "attractions":
            s.add_argument("--family", action="store_true", help="Include kid-friendly types (zoo, aquarium, etc.)")
        if action == "search":
            s.add_argument("--type", required=True, help="Google place type (e.g. cafe, bar, museum)")

    ns = parser.parse_args(args)
    from clawtourism.places import search_restaurants, search_attractions, search_places, format_report

    if ns.action == "restaurants":
        places = search_restaurants(ns.location, ns.radius, ns.min_rating, ns.top)
        print(format_report(places, f"🍽️ Restaurants near {ns.location}"))
    elif ns.action == "attractions":
        places = search_attractions(ns.location, ns.radius, ns.min_rating, ns.top,
                                    family_types=getattr(ns, "family", False))
        print(format_report(places, f"🏛️ Attractions near {ns.location}"))
    elif ns.action == "search":
        places = search_places(ns.location, [ns.type], ns.radius, ns.min_rating, 50, ns.top)
        print(format_report(places, f"📍 {ns.type.title()} near {ns.location}"))


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


def _flights_cmd(args: list[str]):
    import argparse
    parser = argparse.ArgumentParser(prog="clawtourism flights")
    sub = parser.add_subparsers(dest="action")

    s = sub.add_parser("search")
    s.add_argument("--from", required=True, dest="from_code", help="Origin IATA code or city name")
    s.add_argument("--to", required=True, dest="to_code", help="Destination IATA code or city name")
    s.add_argument("--date", required=True, help="Departure date YYYY-MM-DD")
    s.add_argument("--adults", type=int, default=2)
    s.add_argument("--children", type=int, default=0)
    s.add_argument("--direct", action="store_true", help="Direct flights only")
    s.add_argument("--top", type=int, default=8)

    ns = parser.parse_args(args)

    if ns.action == "search":
        from clawtourism.flights import search_flights_report
        result = search_flights_report(
            from_iata=ns.from_code,
            to_iata=ns.to_code,
            depart_date=ns.date,
            adults=ns.adults,
            children=ns.children,
            direct_only=ns.direct,
        )
        print(result)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
