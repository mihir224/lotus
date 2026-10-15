from .storage import get_store


def main() -> None:
    counts = get_store().seed()
    print(
        f"Seeded {counts['documents']} document chunks, {counts['meetings']} meetings, "
        f"{counts['calendar_events']} calendar events, and {counts['board_issues']} board issues."
    )


if __name__ == "__main__":
    main()
