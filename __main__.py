"""Interactive entry point for Fates Engine."""
from orchestrator import orchestrator


def ask(prompt: str, default: str = "") -> str:
    val = input(prompt).strip()
    return val if val else default


def main():
    print("🌟 Fates Engine v2.0")
    print("=" * 60)

    name     = ask("Name: ")
    birth    = ask("Birth date & time (YYYY-MM-DD HH:MM): ")
    location = ask("Birth location (e.g. London, UK): ")
    gender   = ask("Gender [male/female/unspecified]: ", "unspecified")
    output   = ask("Output directory [./reports]: ", "./reports")

    # Optional lat/lon override — needed for small towns Nominatim can't find
    print("\n(Tip: leave blank for major cities — coordinates only needed for small towns)")
    lat_raw  = ask("Latitude override? (press Enter to skip): ")
    lon_raw  = ask("Longitude override? (press Enter to skip): ")

    lat = float(lat_raw) if lat_raw else None
    lon = float(lon_raw) if lon_raw else None

    # Optional focused questions
    print("\n(Optional: up to 5 questions to focus the report — press Enter to skip each)")
    questions = []
    for i in range(1, 6):
        q = ask(f"Question {i}: ")
        if q:
            questions.append(q)
        else:
            break

    print("\n")

    report_path = orchestrator.generate_report(
        birth_datetime=birth,
        location=location,
        gender=gender,
        name=name,
        output_dir=output,
        lat=lat,
        lon=lon,
        user_questions=questions if questions else None
    )

    print(f"\n✨ Done! Report saved to: {report_path}")


if __name__ == "__main__":
    main()
