"""One-time script to generate reference fixture files for import tests.

Run this script to create:
  - tests/fixtures/reference_presentation.pptx
  - tests/fixtures/reference_workbook.xlsx

These are realistic, multi-feature documents used by test_import_reference.py.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from helpers import make_png

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def create_reference_pptx() -> None:
    """Build a realistic multi-slide presentation with diverse content."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()

    # Slide 1: Title slide
    slide1 = prs.slides.add_slide(prs.slide_layouts[0])  # Title Slide
    slide1.shapes.title.text = "Q4 2024 Engineering Review"
    slide1.placeholders[1].text = "Platform Team · December 2024"

    # Slide 2: Formatted body with bold, italic, mixed runs
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Executive Summary"
    tf = slide2.placeholders[1].text_frame
    tf.clear()
    p = tf.paragraphs[0]
    r1 = p.add_run()
    r1.text = "Platform reliability improved to "
    r2 = p.add_run()
    r2.text = "99.95% uptime"
    r2.font.bold = True
    r3 = p.add_run()
    r3.text = ", exceeding the "
    r4 = p.add_run()
    r4.text = "99.9% SLA target"
    r4.font.italic = True
    r5 = p.add_run()
    r5.text = "."

    p2 = tf.add_paragraph()
    p2.text = "Key migrations completed on schedule with zero downtime."

    # Speaker notes
    notes = slide2.notes_slide
    notes.notes_text_frame.text = (
        "Highlight that this is the first quarter we exceeded the SLA. "
        "Mention the database migration specifically."
    )

    # Slide 3: Bullet list with indentation
    slide3 = prs.slides.add_slide(prs.slide_layouts[1])
    slide3.shapes.title.text = "Achievements"
    tf3 = slide3.placeholders[1].text_frame
    tf3.clear()
    items = [
        (0, "Infrastructure"),
        (1, "Migrated to Kubernetes 1.28"),
        (1, "Reduced cloud spend by 18%"),
        (0, "Developer Experience"),
        (1, "CI pipeline reduced from 45min to 12min"),
        (1, "Introduced feature flag system"),
        (2, "Supports gradual rollouts"),
        (2, "A/B testing integration"),
        (0, "Observability"),
        (1, "Deployed distributed tracing"),
        (1, "Alert noise reduced by 60%"),
    ]
    for i, (level, text) in enumerate(items):
        if i == 0:
            tf3.paragraphs[0].text = text
            tf3.paragraphs[0].level = level
        else:
            p = tf3.add_paragraph()
            p.text = text
            p.level = level

    # Slide 4: Table with metrics
    slide4 = prs.slides.add_slide(prs.slide_layouts[1])
    slide4.shapes.title.text = "Performance Metrics"
    tbl = slide4.shapes.add_table(5, 4, Inches(0.5), Inches(2), Inches(9), Inches(3)).table
    headers = ["Service", "P50 (ms)", "P99 (ms)", "Error Rate"]
    data = [
        ["API Gateway", "12", "85", "0.02%"],
        ["Auth Service", "8", "45", "0.01%"],
        ["Data Pipeline", "150", "800", "0.15%"],
        ["Search Index", "25", "200", "0.05%"],
    ]
    for c, h in enumerate(headers):
        tbl.cell(0, c).text = h
    for r, row in enumerate(data, start=1):
        for c, val in enumerate(row):
            tbl.cell(r, c).text = val

    notes4 = slide4.notes_slide
    notes4.notes_text_frame.text = "Data Pipeline P99 is high — discuss optimization plans."

    # Slide 5: Image slide
    slide5 = prs.slides.add_slide(prs.slide_layouts[1])
    slide5.shapes.title.text = "Architecture Overview"
    img_path = FIXTURES_DIR / "_tmp_arch.png"
    img_path.write_bytes(make_png())
    slide5.shapes.add_picture(str(img_path), Inches(1), Inches(2), Inches(4), Inches(3))

    # Slide 6: Hyperlinks
    slide6 = prs.slides.add_slide(prs.slide_layouts[1])
    slide6.shapes.title.text = "Resources"
    tf6 = slide6.placeholders[1].text_frame
    tf6.clear()
    p = tf6.paragraphs[0]
    r = p.add_run()
    r.text = "Project Dashboard"
    r.hyperlink.address = "https://dashboard.example.com"
    p2 = tf6.add_paragraph()
    r2 = p2.add_run()
    r2.text = "Runbook Repository"
    r2.hyperlink.address = "https://github.com/example/runbooks"

    # Slide 7: Blank slide (no title)
    prs.slides.add_slide(prs.slide_layouts[6])

    out = FIXTURES_DIR / "reference_presentation.pptx"
    prs.save(str(out))
    img_path.unlink(missing_ok=True)
    print(f"Created {out}")


def create_reference_xlsx() -> None:
    """Build a realistic multi-sheet workbook with diverse data."""
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)

    # Sheet 1: "Revenue" — mixed types, dates, numbers
    ws1 = wb.create_sheet(title="Revenue")
    ws1.append(["Quarter", "Region", "Revenue ($)", "Growth (%)", "Date"])
    ws1.append(["Q1 2024", "North America", 2100000, 15.2, date(2024, 3, 31)])
    ws1.append(["Q1 2024", "EMEA", 1400000, 12.0, date(2024, 3, 31)])
    ws1.append(["Q1 2024", "APAC", 800000, 22.5, date(2024, 3, 31)])
    ws1.append(["Q2 2024", "North America", 2300000, 18.1, date(2024, 6, 30)])
    ws1.append(["Q2 2024", "EMEA", 1500000, 7.1, date(2024, 6, 30)])
    ws1.append(["Q2 2024", "APAC", 950000, 18.8, date(2024, 6, 30)])

    # Sheet 2: "Headcount" — integer floats, None cells
    ws2 = wb.create_sheet(title="Headcount")
    ws2.append(["Department", "Q1", "Q2", "Q3", "Q4"])
    ws2.append(["Engineering", 120.0, 125.0, 130.0, 150.0])
    ws2.append(["Product", 30.0, 32.0, 35.0, 38.0])
    ws2.append(["Sales", 45.0, None, 50.0, 55.0])
    ws2.append(["Marketing", 20.0, 22.0, None, 25.0])

    # Sheet 3: "Incidents" — pipe chars, timestamps, mixed content
    ws3 = wb.create_sheet(title="Incidents")
    ws3.append(["ID", "Severity", "Description", "Timestamp", "Status"])
    ws3.append(
        [
            "INC-001",
            "P1",
            "Database failover | primary down",
            datetime(2024, 10, 15, 3, 22, 0),
            "Resolved",
        ]
    )
    ws3.append(
        [
            "INC-002",
            "P2",
            "API latency spike | upstream timeout",
            datetime(2024, 10, 20, 14, 5, 0),
            "Resolved",
        ]
    )
    ws3.append(
        [
            "INC-003",
            "P3",
            "Cert renewal failed",
            datetime(2024, 11, 1, 9, 0, 0),
            "Resolved",
        ]
    )
    ws3.append(
        [
            "INC-004",
            "P2",
            "Search index corruption | partial rebuild",
            datetime(2024, 11, 15, 11, 30, 0),
            "Monitoring",
        ]
    )

    # Sheet 4: "Empty" — deliberately blank
    wb.create_sheet(title="Empty")

    # Sheet 5: "Config" — simple key-value, with trailing blanks
    ws5 = wb.create_sheet(title="Config")
    ws5.append(["Setting", "Value"])
    ws5.append(["max_connections", 100])
    ws5.append(["timeout_seconds", 30])
    ws5.append(["retry_count", 3])
    ws5.append(["feature_flags", "dark_mode | beta_api"])
    ws5.append([None, None])
    ws5.append([None, None])

    out = FIXTURES_DIR / "reference_workbook.xlsx"
    wb.save(out)
    print(f"Created {out}")


if __name__ == "__main__":
    create_reference_pptx()
    create_reference_xlsx()
