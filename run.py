from orchestrator import orchestrator

report_path = orchestrator.generate_report(
    birth_datetime="1993-07-19 20:44",
    location="Singapore, Singapore",
    gender="male",
    name="Kyaw Ko Ko",
    output_dir="./reports"
)
print(f"Report saved to: {report_path}")