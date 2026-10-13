from .storage import get_store


def main() -> None:
    counts = get_store().seed()
    print(f"Seeded {counts['documents']} document chunks and {counts['meetings']} meetings.")


if __name__ == "__main__":
    main()
