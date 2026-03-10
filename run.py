from orchestrator import orchestrator

report_path = orchestrator.generate_report(
    birth_datetime="1956-02-04 23:45",
    location="Salin, Magway Region, Myanmar",
    gender="male",
    name="Kyaw Kyaw Wynn",
    output_dir="./reports",
    lat=20.57,
    lon=94.65
)
print(f"Report saved to: {report_path}")
