from .storage import get_store


def main() -> None:
    counts = get_store().seed()
    print(
        f"Seeded {counts['documents']} document chunks, {counts['meetings']} meetings, "
        f"{counts['calendar_events']} calendar events, {counts['board_issues']} board issues, "
        f"{counts.get('projects', 0)} projects, and {counts.get('employees', 0)} employees."
    )


if __name__ == "__main__":
    main()
