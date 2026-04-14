"""
pdf_generator.py — Generate a professional career analysis PDF report.
Uses reportlab only (no external fonts needed).
"""

import os
import tempfile
from datetime import datetime

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER


# Brand colours
PRIMARY   = colors.HexColor("#4F46E5")
SECONDARY = colors.HexColor("#7C3AED")
LIGHT_BG  = colors.HexColor("#F5F3FF")
TEXT_DARK = colors.HexColor("#1E1B4B")
MUTED     = colors.HexColor("#6B7280")


def generate_pdf_report(username: str, filename: str, career: str,
                        skills: list, roadmap: str, courses: list) -> str:
    """Build the PDF, save to a temp file, and return its path."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()

    doc = SimpleDocTemplate(
        tmp.name,
        rightMargin  = 0.75 * inch,
        leftMargin   = 0.75 * inch,
        topMargin    = 0.75 * inch,
        bottomMargin = 0.75 * inch,
    )

    styles = _build_styles()
    story  = []

    # ── Header ──────────────────────────────────
    story.append(Paragraph("Smart Career Guidance", styles["Title"]))
    story.append(Paragraph("AI-Powered Resume Analysis Report", styles["Subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
    story.append(Spacer(1, 0.15 * inch))

    meta = [
        ["Prepared for:", username],
        ["Resume file:",  filename],
        ["Date:",         datetime.now().strftime("%d %B %Y, %I:%M %p")],
    ]
    meta_table = Table(meta, colWidths=[1.5 * inch, 4.5 * inch])
    meta_table.setStyle(TableStyle([
        ("FONT",      (0, 0), (-1, -1), "Helvetica",      9),
        ("FONT",      (0, 0), (0, -1),  "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), MUTED),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.2 * inch))

    # ── Recommended Career ────────────────────
    story.append(_section_header("Recommended Career", styles))
    story.append(Spacer(1, 0.08 * inch))
    career_block = Table(
        [[Paragraph(career, styles["CareerTitle"])]],
        colWidths=[doc.width]
    )
    career_block.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
    ]))
    story.append(career_block)
    story.append(Spacer(1, 0.2 * inch))

    # ── Detected Skills ───────────────────────
    if skills:
        story.append(_section_header("Detected Skills", styles))
        story.append(Spacer(1, 0.08 * inch))

        rows = []
        row  = []
        for i, skill in enumerate(skills):
            row.append(Paragraph(skill, styles["Skill"]))
            if (i + 1) % 4 == 0:
                rows.append(row)
                row = []
        if row:
            while len(row) < 4:
                row.append(Paragraph("", styles["Skill"]))
            rows.append(row)

        skill_table = Table(rows, colWidths=[doc.width / 4] * 4)
        skill_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_BG),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("GRID",          (0, 0), (-1, -1), 0.5, colors.white),
        ]))
        story.append(skill_table)
        story.append(Spacer(1, 0.2 * inch))

    # ── Preparation Roadmap ───────────────────
    if roadmap:
        story.append(_section_header("Preparation Roadmap", styles))
        story.append(Spacer(1, 0.08 * inch))
        for line in roadmap.split("\n"):
            line = line.strip()
            if line:
                story.append(Paragraph(line, styles["RoadmapStep"]))
                story.append(Spacer(1, 0.04 * inch))
        story.append(Spacer(1, 0.1 * inch))

    # ── Suggested Courses ─────────────────────
    if courses:
        story.append(_section_header("Suggested Courses", styles))
        story.append(Spacer(1, 0.08 * inch))

        course_data = [["#", "Course", "Platform"]]
        for i, c in enumerate(courses, 1):
            if isinstance(c, dict):
                course_data.append([str(i), c.get("title", ""), c.get("platform", "")])
            else:
                course_data.append([str(i), str(c), ""])

        course_table = Table(course_data,
                             colWidths=[0.3 * inch, 4.2 * inch, 1.5 * inch])
        course_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  PRIMARY),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
            ("FONT",          (0, 0), (-1, 0),  "Helvetica-Bold", 9),
            ("FONT",          (0, 1), (-1, -1), "Helvetica", 9),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ("ALIGN",         (0, 0), (0, -1),  "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ]))
        story.append(course_table)

    # ── Footer ────────────────────────────────
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=MUTED))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(
        "Generated by Smart Career Guidance · AI-powered resume analysis",
        styles["Footer"]
    ))

    doc.build(story)
    return tmp.name


# ─────────────────────────────────────────────
# Style helpers
# ─────────────────────────────────────────────

def _build_styles():
    s = {}
    s["Title"] = ParagraphStyle(
        "Title", fontSize=22, textColor=PRIMARY,
        fontName="Helvetica-Bold", alignment=TA_LEFT, spaceAfter=4
    )
    s["Subtitle"] = ParagraphStyle(
        "Subtitle", fontSize=11, textColor=MUTED,
        fontName="Helvetica", alignment=TA_LEFT, spaceAfter=8
    )
    s["SectionHeader"] = ParagraphStyle(
        "SectionHeader", fontSize=13, textColor=PRIMARY,
        fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=2
    )
    s["CareerTitle"] = ParagraphStyle(
        "CareerTitle", fontSize=16, textColor=TEXT_DARK,
        fontName="Helvetica-Bold"
    )
    s["Skill"] = ParagraphStyle(
        "Skill", fontSize=9, textColor=TEXT_DARK,
        fontName="Helvetica", alignment=TA_CENTER
    )
    s["RoadmapStep"] = ParagraphStyle(
        "RoadmapStep", fontSize=10, textColor=TEXT_DARK,
        fontName="Helvetica", leftIndent=10, leading=14
    )
    s["Footer"] = ParagraphStyle(
        "Footer", fontSize=8, textColor=MUTED,
        fontName="Helvetica", alignment=TA_CENTER
    )
    return s


def _section_header(title: str, styles: dict):
    return Paragraph(f"▌ {title}", styles["SectionHeader"])
