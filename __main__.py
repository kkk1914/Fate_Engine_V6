"""Interactive entry point for Fates Engine."""
from orchestrator import orchestrator
from config import settings


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

    # Language selection
    lang = ask("Report language [en/my] (default: en): ", "en").lower()
    if lang not in ("en", "my"):
        lang = "en"

    # Report part selection
    PART_MAP = {
        "1": ("I",  "THE NATIVITY"),
        "2": ("II", "THE FIFTEEN-YEAR ALMANAC"),
        "3": ("IV", "YOUR QUESTIONS"),
    }
    print("\nWhich report parts would you like?")
    print("  1. THE NATIVITY          (natal portrait)")
    print("  2. THE FIFTEEN-YEAR ALMANAC (predictive almanac)")
    print("  3. YOUR QUESTIONS        (personalised Q&A)")
    print("  Press Enter for all parts.")
    parts_raw = ask("Select parts (e.g. 1,3 or Enter for all): ")
    if parts_raw:
        chosen = set()
        for ch in parts_raw.replace(" ", "").split(","):
            if ch in PART_MAP:
                chosen.add(PART_MAP[ch][0])
        if chosen:
            settings.include_parts = sorted(chosen)
            selected_names = [PART_MAP[ch][1] for ch in sorted(parts_raw.replace(" ", "").split(",")) if ch in PART_MAP]
            print(f"  → Generating: {', '.join(selected_names)}")
        else:
            print("  → Invalid selection, generating all parts.")
            settings.include_parts = ["I", "II", "III", "IV"]
    else:
        settings.include_parts = ["I", "II", "III", "IV"]

    # Optional focused questions
    if "IV" in settings.include_parts:
        if lang == "my":
            print("\n(Optional: up to 5 questions — English or Burmese both accepted)")
        else:
            print("\n(Optional: up to 5 questions to focus the report — press Enter to skip each)")
        questions = []
        for i in range(1, 6):
            q = ask(f"Question {i}: ")
            if q:
                questions.append(q)
            else:
                break
    else:
        questions = []

    print("\n")

    report_path = orchestrator.generate_report(
        birth_datetime=birth,
        location=location,
        gender=gender,
        name=name,
        output_dir=output,
        lat=lat,
        lon=lon,
        user_questions=questions if questions else None,
        language=lang,
    )

    print(f"\n✨ Done! Report saved to: {report_path}")


if __name__ == "__main__":
    main()
