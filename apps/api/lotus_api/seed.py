from .storage import get_store


def main() -> None:
    counts = get_store().seed()
    print(
        f"Seeded {counts['documents']} document chunks, {counts['meetings']} meetings, "
        f"and {counts['calendar_events']} calendar events."
    )


if __name__ == "__main__":
    main()
