#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Inject thesis markdown content into the TULIBS .docx template.

Reads all thesis/*.md chapters and fills the TULIBS template using the
correct TU_* styles. Preserves the template's formatting, fonts, page
layout, headers/footers, and section breaks.

Style mapping:
  # Chapter X: Title       → Heading 1
  ## X.Y Section            → TU_Main Heading_ChapterX
  ### X.Y.Z Subsection      → TU_Sub-heading 1
  #### X.Y.Z.W Detail       → TU_Sub-heading 2
  ##### X.Y.Z.W.V           → TU_Sub-heading 3
  Body text                  → TU_Paragraph_Normal
  Code blocks                → TU_Paragraph_Normal (Consolas font)
  Tables                     → Word tables with Table Grid style
  [Figure X.Y: ...]          → TU_Paragraph_Normal (centered, italic)
  $$LaTeX$$                  → TU_Paragraph_Normal (Cambria Math, centered)

Usage:
    python scripts/inject_into_template.py
"""
import os
import sys
import re
import copy
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

THESIS_DIR = Path(__file__).parent.parent / "thesis"
TEMPLATE_PATH = THESIS_DIR / "TULIBS_Thesis-template-Thai_rev_2024.docx"
OUTPUT_PATH = THESIS_DIR / "thesis_final.docx"

CHAPTER_FILES = [
    "CH1_Introduction.md",
    "CH2_Literature_Review.md",
    "CH3_Methodology.md",
    "CH4_System_Design.md",
    "CH5_Implementation.md",
    "CH6_Testing_and_Evaluation.md",
    "CH7_Discussion.md",
    "CH8_Conclusion.md",
]

APPENDIX_FILES = [
    "AP_A_Test_Results.md",
    "AP_B_User_Manual.md",
]

REFERENCES_FILE = "REFERENCES.md"

# Abstract text
ABSTRACT_EN = """This thesis presents the design, implementation, and evaluation of an AI-powered virtual assistant for The Grand Horizon Hotel, a luxury 5-star hotel in Thailand. The system employs a LangGraph-based multi-agent architecture with four specialized sub-agents for booking operations, hotel services, knowledge retrieval, and general conversation, all supporting bilingual Thai and English interaction.

The backend is built with FastAPI and integrates Retrieval-Augmented Generation (RAG) using Qdrant vector embeddings over a hotel knowledge base of 10 documents. The system supports runtime switching between a local 9-billion-parameter LLM (Qwen3.5 Opus 9B on Ollama) and a cloud-hosted model (Qwen3 Max on OpenRouter), enabling hotels to balance cost, privacy, and capability based on traffic demands.

Production-grade features include JWT authentication with role-based access control, login rate limiting, account lockout, audit logging, PII redaction, and five chat scaling primitives. The frontend is built with Next.js 15 and Ant Design 5, featuring a real-time chat interface with SSE streaming and an admin dashboard.

Evaluation across 25 hotel-domain test cases shows the local 9B model achieves 92% accuracy (23/25) compared to 100% (25/25) for the cloud model. Infrastructure testing covers 193 automated assertions, all passing. Performance optimization reduced warm chat latency from 18 seconds to 5 seconds."""

KEYWORDS_EN = "hotel AI, virtual assistant, LangGraph, multi-agent system, RAG, Qdrant, LLM, Ollama, FastAPI, Next.js, bilingual chatbot"
KEYWORDS_TH = "ปัญญาประดิษฐ์โรงแรม, ผู้ช่วยเสมือน, LangGraph, ระบบหลายตัวแทน, RAG, Qdrant, LLM, Ollama, FastAPI, Next.js, แชทบอทสองภาษา"


# =============================================================================
# Markdown parser
# =============================================================================


def parse_markdown(md_text: str, chapter_num: int) -> List[Dict]:
    """Parse markdown into structured elements with style hints."""
    elements = []
    lines = md_text.split("\n")
    i = 0
    in_code = False
    code_lines = []
    code_lang = ""

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Code blocks
        if stripped.startswith("```"):
            if in_code:
                elements.append({
                    "type": "code",
                    "content": "\n".join(code_lines),
                    "lang": code_lang,
                })
                in_code = False
                code_lines = []
                code_lang = ""
            else:
                in_code = True
                code_lang = stripped[3:].strip()
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        # LaTeX equations
        if stripped.startswith("$$"):
            latex = stripped[2:]
            if stripped.endswith("$$") and len(stripped) > 4:
                elements.append({"type": "latex", "content": latex[:-2]})
            else:
                eq_parts = [latex]
                i += 1
                while i < len(lines):
                    if lines[i].strip().endswith("$$"):
                        eq_parts.append(lines[i].strip()[:-2])
                        break
                    eq_parts.append(lines[i].strip())
                    i += 1
                elements.append({"type": "latex", "content": " ".join(eq_parts)})
            i += 1
            continue

        # Headings
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped[level:].strip()
            # Clean ** from headings
            text = text.replace("**", "")
            elements.append({
                "type": "heading",
                "level": level,
                "content": text,
                "chapter": chapter_num,
            })
            i += 1
            continue

        # Tables
        if stripped.startswith("|"):
            table_rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                if not re.match(r'^\|[\s\-:|]+\|$', row):
                    cells = [c.strip().replace("**", "") for c in row.split("|")[1:-1]]
                    table_rows.append(cells)
                i += 1
            if table_rows:
                elements.append({"type": "table", "rows": table_rows})
            continue

        # Figure placeholders
        if stripped.startswith("[Figure"):
            elements.append({"type": "figure", "content": stripped})
            i += 1
            continue

        # Horizontal rules
        if stripped == "---":
            elements.append({"type": "hr"})
            i += 1
            continue

        # Bullet points
        if stripped.startswith("- ") or stripped.startswith("* "):
            elements.append({"type": "bullet", "content": stripped[2:]})
            i += 1
            continue

        # Numbered items
        m = re.match(r'^(\d+)\.\s+(.*)', stripped)
        if m:
            elements.append({"type": "numbered", "content": m.group(2)})
            i += 1
            continue

        # Empty lines
        if not stripped:
            i += 1
            continue

        # Regular paragraph
        elements.append({"type": "paragraph", "content": stripped})
        i += 1

    return elements


# =============================================================================
# Rich text rendering (bold, italic, code within a paragraph)
# =============================================================================


def add_rich_runs(paragraph, text: str):
    """Add runs with **bold**, *italic*, and `code` formatting."""
    # Clear existing runs
    for run in paragraph.runs:
        run.text = ""

    parts = re.split(r'(\*\*.*?\*\*|\*.*?\*|`.*?`)', text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part.startswith("*") and part.endswith("*") and not part.startswith("**"):
            run = paragraph.add_run(part[1:-1])
            run.italic = True
        elif part.startswith("`") and part.endswith("`"):
            run = paragraph.add_run(part[1:-1])
            run.font.name = 'Consolas'
            run.font.size = Pt(12)
        else:
            paragraph.add_run(part)


# =============================================================================
# Main injection logic
# =============================================================================


def get_main_heading_style(chapter_num: int) -> str:
    """Get the correct TU_Main Heading style for a chapter number."""
    if chapter_num == 1:
        return "TU_Main Heading _Chapter1"  # note the space before _Chapter1
    else:
        return f"TU_Main Heading_Chapter{chapter_num}"


def inject_elements(doc: Document, elements: List[Dict], insert_before_idx: int) -> int:
    """Inject parsed elements into the document at a specific position.

    Returns the number of paragraphs added.
    """
    added = 0

    for elem in elements:
        etype = elem["type"]

        if etype == "heading":
            level = elem["level"]
            chapter = elem.get("chapter", 1)
            text = elem["content"]

            if level == 1:
                # Chapter title → Heading 1
                p = doc.add_paragraph(text, style="Heading 1")
            elif level == 2:
                # Main section → TU_Main Heading_ChapterX
                style_name = get_main_heading_style(chapter)
                try:
                    p = doc.add_paragraph(text, style=style_name)
                except KeyError:
                    p = doc.add_paragraph(text, style="Heading 2")
            elif level == 3:
                # Subsection → TU_Sub-heading 1
                p = doc.add_paragraph(text, style="TU_Sub-heading 1")
            elif level == 4:
                # Sub-subsection → TU_Sub-heading 2
                p = doc.add_paragraph(text, style="TU_Sub-heading 2")
            elif level >= 5:
                # Sub-sub-subsection → TU_Sub-heading 3
                p = doc.add_paragraph(text, style="TU_Sub-heading 3")
            added += 1

        elif etype == "paragraph":
            p = doc.add_paragraph(style="TU_Paragraph_Normal")
            add_rich_runs(p, elem["content"])
            added += 1

        elif etype == "bullet":
            p = doc.add_paragraph(style="TU_Paragraph_Normal")
            add_rich_runs(p, "• " + elem["content"])
            added += 1

        elif etype == "numbered":
            p = doc.add_paragraph(style="TU_Paragraph_Normal")
            add_rich_runs(p, elem["content"])
            added += 1

        elif etype == "code":
            content = elem["content"]
            # Source file reference if first line is a path comment
            source_ref = ""
            code_lines = content.split("\n")
            if code_lines and code_lines[0].strip().startswith("#"):
                fm = re.match(r'^#\s*(src/\S+|deploy/\S+)', code_lines[0].strip())
                if fm:
                    source_ref = fm.group(1)
                    code_lines = code_lines[1:]

            if source_ref:
                p = doc.add_paragraph(style="TU_Paragraph_Normal")
                run = p.add_run(f"[Source: {source_ref}]")
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
                run.italic = True
                added += 1

            for code_line in code_lines:
                p = doc.add_paragraph(style="TU_Paragraph_Normal")
                pf = p.paragraph_format
                pf.left_indent = Cm(1)
                pf.space_before = Pt(0)
                pf.space_after = Pt(0)
                run = p.add_run(code_line)
                run.font.name = 'Consolas'
                run.font.size = Pt(10)
                added += 1

        elif etype == "table":
            rows = elem["rows"]
            if rows:
                max_cols = max(len(r) for r in rows)
                try:
                    tbl = doc.add_table(rows=len(rows), cols=max_cols)
                    tbl.style = 'Table Grid'
                    for ri, row in enumerate(rows):
                        for ci, cell in enumerate(row):
                            if ci < max_cols:
                                tbl.rows[ri].cells[ci].text = cell
                                if ri == 0:
                                    for para in tbl.rows[ri].cells[ci].paragraphs:
                                        for run in para.runs:
                                            run.bold = True
                except Exception as e:
                    p = doc.add_paragraph(f"[Table error: {e}]", style="TU_Paragraph_Normal")
                added += 1

        elif etype == "figure":
            p = doc.add_paragraph(style="TU_Paragraph_Normal")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run("━" * 30 + "\n")
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
            run = p.add_run(elem["content"])
            run.italic = True
            run.font.size = Pt(11)
            run = p.add_run("\n[Insert diagram here / แทรกภาพที่นี่]")
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(0xCC, 0x00, 0x00)
            run = p.add_run("\n" + "━" * 30)
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
            added += 1

        elif etype == "latex":
            latex = elem["content"]
            # Convert to Unicode
            unicode_map = {
                r'\kappa': 'κ', r'\alpha': 'α', r'\beta': 'β',
                r'\gamma': 'γ', r'\delta': 'δ', r'\sigma': 'σ',
                r'\mu': 'μ', r'\pi': 'π', r'\theta': 'θ',
                r'\leq': '≤', r'\geq': '≥', r'\neq': '≠',
                r'\times': '×', r'\cdot': '·', r'\infty': '∞',
            }
            rendered = latex
            for tex, uni in unicode_map.items():
                rendered = rendered.replace(tex, uni)
            rendered = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1) / (\2)', rendered)
            rendered = re.sub(r'\\(\w+)', r'\1', rendered)
            rendered = rendered.replace('{', '').replace('}', '')

            p = doc.add_paragraph(style="TU_Paragraph_Normal")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(rendered)
            run.font.name = 'Cambria Math'
            run.font.size = Pt(14)
            run.italic = True
            added += 1

        elif etype == "hr":
            p = doc.add_paragraph(style="TU_Paragraph_Normal")
            run = p.add_run("─" * 40)
            run.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
            run.font.size = Pt(8)
            added += 1

    return added


def clear_placeholder_content(doc: Document, start_idx: int, end_idx: int):
    """Remove placeholder paragraphs between start and end indices."""
    # We'll mark paragraphs for removal by clearing their text
    # (can't delete paragraphs easily in python-docx, but we can empty them)
    for i in range(start_idx, min(end_idx, len(doc.paragraphs))):
        p = doc.paragraphs[i]
        text = p.text.strip()
        if text in ("เริ่มพิมพ์เนื้อหา", "เริ่มพิมพ์ย่อหน้าใหม่",
                     "Insert text here", "หัวข้อใหญ่",
                     "หัวข้อย่อยระดับที่ 1", "หัวข้อย่อยระดับที่ 2",
                     "หัวข้อย่อยระดับที่ 3"):
            for run in p.runs:
                run.text = ""


def main():
    print("=" * 60)
    print("Thesis Template Injector — TULIBS Format")
    print("=" * 60)

    if not TEMPLATE_PATH.exists():
        print(f"ERROR: Template not found: {TEMPLATE_PATH}")
        sys.exit(1)

    # Load template
    print(f"Loading template: {TEMPLATE_PATH.name}")
    doc = Document(str(TEMPLATE_PATH))
    print(f"  {len(doc.paragraphs)} paragraphs, {len(doc.styles)} styles")

    # Step 1: Fill abstract
    print("\nFilling abstract...")
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if text == "Insert text here" and p.style.name == "TU_Paragraph_Normal":
            # Check if this is in the ABSTRACT section
            # Look back for "ABSTRACT" heading
            for j in range(max(0, i-5), i):
                if "ABSTRACT" in doc.paragraphs[j].text:
                    for run in p.runs:
                        run.text = ""
                    p.add_run(ABSTRACT_EN)
                    print(f"  Filled English abstract at P{i}")
                    break

        if text.startswith("Keywords: Insert"):
            for run in p.runs:
                run.text = ""
            p.add_run(f"Keywords: {KEYWORDS_EN}")
            print(f"  Filled English keywords at P{i}")

        if text.startswith("คำสำคัญ: พิมพ์"):
            for run in p.runs:
                run.text = ""
            p.add_run(f"คำสำคัญ: {KEYWORDS_TH}")
            print(f"  Filled Thai keywords at P{i}")

    # Step 2: Process each chapter — append content after each Heading 1
    print("\nProcessing chapters...")

    for ch_idx, ch_file in enumerate(CHAPTER_FILES):
        ch_num = ch_idx + 1
        ch_path = THESIS_DIR / ch_file
        if not ch_path.exists():
            print(f"  [SKIP] {ch_file}")
            continue

        md_text = ch_path.read_text(encoding="utf-8")
        elements = parse_markdown(md_text, ch_num)

        # Skip the first element if it's the chapter title heading
        # (the template already has Heading 1 for each chapter)
        if elements and elements[0]["type"] == "heading" and elements[0]["level"] == 1:
            # Update the existing Heading 1 text in the template
            chapter_title = elements[0]["content"]
            elements = elements[1:]  # skip it from injection

            # Find the corresponding Heading 1 in template and update its text
            heading_count = 0
            for p in doc.paragraphs:
                if p.style.name == "Heading 1":
                    heading_count += 1
                    if heading_count == ch_num:
                        for run in p.runs:
                            run.text = ""
                        p.add_run(chapter_title)
                        break

        # Inject all remaining elements at the end of the document
        # (simpler than trying to insert at exact positions)
        count = inject_elements(doc, elements, 0)
        print(f"  [CH{ch_num}] {ch_file}: {len(elements)} elements → {count} paragraphs added")

    # Step 3: Process appendices
    print("\nProcessing appendices...")
    for ap_idx, ap_file in enumerate(APPENDIX_FILES):
        ap_path = THESIS_DIR / ap_file
        if not ap_path.exists():
            print(f"  [SKIP] {ap_file}")
            continue

        md_text = ap_path.read_text(encoding="utf-8")
        elements = parse_markdown(md_text, 0)  # chapter 0 for appendices

        count = inject_elements(doc, elements, 0)
        print(f"  [AP{ap_idx+1}] {ap_file}: {len(elements)} elements → {count} paragraphs added")

    # Step 4: Process references
    print("\nProcessing references...")
    ref_path = THESIS_DIR / REFERENCES_FILE
    if ref_path.exists():
        md_text = ref_path.read_text(encoding="utf-8")
        elements = parse_markdown(md_text, 0)
        count = inject_elements(doc, elements, 0)
        print(f"  [REF] {REFERENCES_FILE}: {len(elements)} elements → {count} paragraphs added")

    # Step 5: Save
    doc.save(str(OUTPUT_PATH))
    file_size = os.path.getsize(str(OUTPUT_PATH)) / 1024
    print(f"\n{'=' * 60}")
    print(f"Saved: {OUTPUT_PATH} ({file_size:.0f} KB)")
    print(f"{'=' * 60}")
    print(f"\nOpen in Word, then:")
    print(f"  1. Update Table of Contents (right-click → Update Field)")
    print(f"  2. Search for 'แทรกภาพที่นี่' to find figure placeholders")
    print(f"  3. Fill in university/author info on cover pages")
    print(f"  4. Delete template placeholder text that wasn't replaced")


if __name__ == "__main__":
    main()
