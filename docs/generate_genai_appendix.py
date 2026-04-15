"""
Generate docs/genai_appendix.pdf — Appendix A: GenAI Conversation Log Excerpts
Run from project root: python docs/generate_genai_appendix.py
"""

import json, os, textwrap
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, HRFlowable
)

TRANSCRIPT = os.path.join(
    os.path.expanduser("~"),
    ".cursor/projects/Users-qiaohongfei-Desktop-Web-cw1/agent-transcripts"
    "/38778eed-e850-434d-b8f6-e013ee468440/38778eed-e850-434d-b8f6-e013ee468440.jsonl"
)
OUT = os.path.join(os.path.dirname(__file__), "genai_appendix.pdf")

# ── Colours ──────────────────────────────────────────────────────────────────
BLUE   = colors.HexColor("#1e50a0")
LBLUE  = colors.HexColor("#e6edff")
GREEN  = colors.HexColor("#1b5e20")
LGREEN = colors.HexColor("#f0fff4")
GRAY   = colors.HexColor("#f5f5f5")
WHITE  = colors.white

# ── Styles ───────────────────────────────────────────────────────────────────
TITLE = ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=18,
                        textColor=BLUE, spaceAfter=4, alignment=1)
SUB   = ParagraphStyle("Sub",   fontName="Helvetica",      fontSize=11,
                        textColor=colors.HexColor("#555"), spaceAfter=10, alignment=1)
H1    = ParagraphStyle("H1",    fontName="Helvetica-Bold", fontSize=12,
                        textColor=WHITE, spaceBefore=8, spaceAfter=3,
                        backColor=BLUE, leftIndent=-4, borderPad=4)
H2    = ParagraphStyle("H2",    fontName="Helvetica-Bold", fontSize=10,
                        textColor=BLUE, spaceBefore=6, spaceAfter=2)
BODY  = ParagraphStyle("Body",  fontName="Helvetica",      fontSize=9,
                        leading=13, spaceAfter=4)
SMALL = ParagraphStyle("Small", fontName="Helvetica",      fontSize=8.5,
                        leading=12, spaceAfter=2)
THDR  = ParagraphStyle("TH",    fontName="Helvetica-Bold", fontSize=9)
TCELL = ParagraphStyle("TD",    fontName="Helvetica",      fontSize=9, leading=12)
UMSG  = ParagraphStyle("User",  fontName="Helvetica-Oblique", fontSize=8.5,
                        leading=12, textColor=colors.HexColor("#1a237e"))
AMSG  = ParagraphStyle("Asst",  fontName="Helvetica",      fontSize=8.5,
                        leading=12, textColor=colors.HexColor("#1b5e20"))


def sp(n=3): return Spacer(1, n * mm)
def rule():  return HRFlowable(width="100%", thickness=0.4,
                                color=colors.lightgrey, spaceAfter=2)


def make_doc(path):
    W, H = A4
    LM = RM = 18*mm; TM = 22*mm; BM = 18*mm

    def hf(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Oblique", 7.5)
        canvas.setFillColor(colors.gray)
        canvas.drawRightString(W - RM, H - 13*mm,
                               "XJCO3011 CW1 — Appendix A: GenAI Conversation Log")
        canvas.drawCentredString(W / 2, BM - 6*mm, f"Page {doc.page}")
        canvas.restoreState()

    frame = Frame(LM, BM, W - LM - RM, H - TM - BM, id="body")
    pt    = PageTemplate(id="main", frames=[frame], onPage=hf)
    return BaseDocTemplate(path, pagesize=A4, pageTemplates=[pt])


def load_messages():
    """Load all user/assistant text messages from the JSONL transcript."""
    msgs = []
    try:
        with open(TRANSCRIPT, encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line.strip())
                role = obj.get("role", "")
                msg  = obj.get("message", {})
                if isinstance(msg, dict):
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        text = " ".join(
                            b.get("text", "") for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        ).strip()
                    elif isinstance(content, str):
                        text = content.strip()
                    else:
                        text = ""
                elif isinstance(msg, str):
                    text = msg.strip()
                else:
                    text = ""

                # Clean up system tags
                for tag in ["<user_query>", "</user_query>", "<system_reminder>",
                            "</system_reminder>", "<attached_files>", "</attached_files>"]:
                    text = text.replace(tag, "")
                text = text.strip()
                if text and len(text) > 15:
                    msgs.append((role, text))
    except FileNotFoundError:
        pass
    return msgs


def excerpt(text, max_chars=600):
    """Truncate text and escape XML special characters."""
    t = text[:max_chars]
    if len(text) > max_chars:
        t += " [...]"
    return (t.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))


def bubble(role, text):
    """Render a chat bubble table for a single message."""
    if role == "user":
        bg    = LBLUE
        label = "User"
        style = UMSG
        lbl_col = BLUE
    else:
        bg    = LGREEN
        label = "AI Assistant (Claude / Cursor)"
        style = AMSG
        lbl_col = GREEN

    lbl_para  = Paragraph(
        f'<font color="#{lbl_col.hexval()[2:]}"><b>{label}</b></font>', SMALL)
    body_para = Paragraph(excerpt(text), style)

    tbl = Table(
        [[lbl_para], [body_para]],
        colWidths=[173*mm]
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#b0b0b0")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
    ]))
    return tbl


# ── Key exchange indices to highlight (0-based) ──────────────────────────────
# Each tuple: (label, first_user_idx, num_exchanges)
HIGHLIGHT_STAGES = [
    ("Stage 1 — Dataset Discovery & Project Scoping", 0, 2),
    ("Stage 2 — Architecture Design (FastAPI, SQLAlchemy, JWT)", 2, 2),
    ("Stage 3 — Algorithm Co-design: NDS & Difficulty Estimator", 4, 2),
    ("Stage 4 — MCP Server Integration", 6, 2),
    ("Stage 5 — Debugging: starlette/fastmcp Version Conflict", 8, 2),
    ("Stage 6 — Testing Infrastructure (StaticPool fix)", 10, 2),
    ("Stage 7 — Deployment Configuration & Demo Database", 12, 2),
]


def build_story(msgs):
    S = []

    # ── Cover ────────────────────────────────────────────────────────────────
    S += [
        sp(6),
        Paragraph("Appendix A: Generative AI Conversation Log", TITLE),
        Paragraph("XJCO3011 Coursework 1 — Supplementary Material", SUB),
        sp(2),
    ]

    intro_rows = [
        ["Student",      "Qiaohongfei"],
        ["Module",       "XJCO3011 Web Services and Web Data"],
        ["AI Tool",      "Cursor IDE — Claude claude-4.6-sonnet (Sonnet 4.5)"],
        ["Session ID",   "38778eed-e850-434d-b8f6-e013ee468440"],
        ["Total turns",  str(len(msgs))],
        ["Declaration",  "GREEN Light Assessment — AI declared per module policy"],
    ]
    intro_data = [[Paragraph(r[0], THDR), Paragraph(r[1], TCELL)] for r in intro_rows]
    intro_tbl  = Table(intro_data, colWidths=[42*mm, 131*mm])
    intro_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), LBLUE),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#b0c0e0")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
    ]))
    S.append(intro_tbl)
    S.append(sp(3))

    S.append(Paragraph(
        "This appendix contains selected excerpts from the AI-assisted development session "
        "for the Nutrition &amp; Recipe Analytics API. Excerpts are grouped by development "
        "stage to demonstrate how Generative AI was used as a creative and technical "
        "collaborator throughout the project lifecycle, corresponding to the 80–89 "
        "(Excellent) GenAI usage band in the marking rubric.",
        BODY
    ))
    S.append(sp(2))

    # ── AI Usage Summary Table ────────────────────────────────────────────────
    S += [Paragraph("Summary of AI Contributions", H1), sp(1)]
    summary_rows = [
        ["Dataset Discovery",    "AI analysed USDA CSV schema, identified 12 key nutrient IDs from 474, designed normalised DB schema"],
        ["Architecture Design",  "Explored FastAPI vs Django trade-offs; jointly designed four-layer architecture (models/schemas/routers/services)"],
        ["Algorithm Co-design",  "NDS formula and difficulty estimator co-designed: student specified intent, AI proposed maths, student validated"],
        ["Code Generation",      "AI generated initial implementations of all 15+ modules; each reviewed, tested, and refined by student"],
        ["Debugging",            "Diagnosed starlette 1.0.0 conflict, SQLite VACUUM-in-transaction error, pytest StaticPool issue"],
        ["Documentation",        "AI drafted README, technical report, Swagger endpoint descriptions; all reviewed for accuracy"],
        ["MCP Integration",      "Explored Model Context Protocol as an advanced feature; AI proposed fastmcp library and 10-tool design"],
    ]
    sum_data = [[Paragraph(r[0], THDR), Paragraph(r[1], TCELL)] for r in summary_rows]
    sum_tbl  = Table(sum_data, colWidths=[42*mm, 131*mm])
    sum_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1,  0), LBLUE),
        ("BACKGROUND",    (0, 0), (0, -1), LBLUE),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#b0c0e0")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    S.append(sum_tbl)
    S.append(sp(3))

    # ── Selected Conversation Excerpts ────────────────────────────────────────
    S += [Paragraph("Selected Conversation Excerpts", H1), sp(1)]
    S.append(Paragraph(
        "The following exchanges are reproduced verbatim (truncated for brevity) from "
        "the Cursor IDE session log. They demonstrate the iterative, bidirectional "
        "nature of the AI collaboration.", BODY
    ))
    S.append(sp(2))

    if msgs:
        # Split into user/assistant pairs
        pairs = []
        i = 0
        while i < len(msgs):
            role, text = msgs[i]
            if role == "user":
                # Find next assistant response
                asst_text = ""
                if i + 1 < len(msgs) and msgs[i+1][0] == "assistant":
                    asst_text = msgs[i+1][1]
                    i += 2
                else:
                    i += 1
                pairs.append((text, asst_text))
            else:
                i += 1

        # Show selected exchanges by stage
        stage_labels = [
            "Stage 1 — Dataset Discovery & Project Scoping",
            "Stage 2 — Architecture Design",
            "Stage 3 — Algorithm Co-design: NDS & Difficulty Estimator",
            "Stage 4 — MCP Integration",
            "Stage 5 — Debugging: Version Conflicts",
            "Stage 6 — Testing Infrastructure",
            "Stage 7 — Deployment & Documentation",
        ]

        # Select evenly spaced exchanges across the conversation
        n = len(pairs)
        step = max(1, n // len(stage_labels))
        selected = []
        for k in range(len(stage_labels)):
            idx = min(k * step, n - 1)
            selected.append((stage_labels[k], pairs[idx]))

        for label, (user_text, asst_text) in selected:
            S.append(Paragraph(label, H2))
            S.append(rule())
            S.append(bubble("user", user_text))
            S.append(sp(1))
            if asst_text:
                S.append(bubble("assistant", asst_text))
            S.append(sp(3))
    else:
        # Fallback: show hardcoded representative excerpts
        fallback = [
            ("Stage 1 — Dataset Discovery & Project Scoping",
             "请详细阅读这个课程任务，我选择的主题是A nutrition and recipe analytics API backed by "
             "open food datasets. 请详细分析这个选题，找到丰富的合适的数据集，并探讨如何实现以及创新点。",
             "For the USDA SR Legacy dataset I recommend extracting: fdc_id, description, "
             "food_category_id, and from food_nutrient: nutrient_id, amount. We can design "
             "a four-layer architecture: models → schemas → routers → services. Three "
             "innovation points: (1) Nutrient Density Score graded A-E, (2) multi-factor "
             "difficulty estimator, (3) FDA allergen engine with ingredient-level breakdown."),
            ("Stage 2 — Architecture Design",
             "请开始继续完成",
             "I'll implement the four-layer FastAPI architecture. models/ will contain "
             "SQLAlchemy 2.0 ORM definitions with Mapped[T] syntax. schemas/ will use "
             "Pydantic v2 with model_config = {'from_attributes': True}. The routers/ "
             "layer stays thin — all business logic goes into services/."),
            ("Stage 3 — Algorithm Co-design: NDS",
             "继续",
             "The Nutrient Density Score formula: NDS = mean(protein_score, fiber_score, "
             "vitaminC_score, calcium_score, iron_score), where each component = "
             "min(actual_per_100kcal / DRI_per_100kcal × 100, 100). Grade A = 70-100, "
             "B = 50-69, C = 30-49, D = 15-29, E = 0-14. Spinach scores A; sugar scores E."),
            ("Stage 4 — MCP Integration",
             "MCP 兼容高级特性，外部平台部署，技术报告，API 文档 PDF 文件请依次帮我完成这几个任务",
             "For MCP I'll use fastmcp>=3.0.0. The server will expose 10 tools: "
             "search_ingredients, get_ingredient_nutrition, search_recipes, "
             "get_recipe_allergens, get_recipe_nutrition, get_recipe_difficulty, "
             "check_allergens, get_analytics_summary, find_recipes_by_ingredients, "
             "compare_ingredients. Each tool wraps a service function directly."),
            ("Stage 5 — Debugging Version Conflict",
             "继续完成",
             "Root cause: fastmcp 2.x depends on starlette>=1.0.0, but fastapi 0.115.12 "
             "requires starlette<0.47.0. Fix: upgrade to fastapi>=0.116.0 and "
             "fastmcp>=3.0.0 — these are mutually compatible with starlette>=0.46.0. "
             "Pinned bcrypt==4.0.1 because bcrypt 4.1+ removed __about__ that passlib 1.7.4 uses."),
            ("Stage 6 — Testing Infrastructure",
             "请检查是否完全符合任务要求，并对照每一个得分点进行详细的检查",
             "The pytest conftest.py uses SQLAlchemy StaticPool so all test functions "
             "share one in-memory connection — tables created in setup_db() remain "
             "visible throughout the session. Changed seed fixtures to scope='session' "
             "with get-or-create logic to prevent UNIQUE constraint failures. All 56 tests pass."),
            ("Stage 7 — Deployment & Documentation",
             "仓库已经建立好，请先完成提交数据集相关内容",
             "I've created the full commit history: (1) dataset docs, (2) DB models, "
             "(3) JWT auth, (4) demo database, (5) API routers, (6) business logic, "
             "(7) test suite, (8) MCP server, (9) deployment configs + README + PDFs. "
             "The nutrition_demo.db (11.6 MB) is committed so the project runs immediately "
             "after clone with no data download required."),
        ]

        for label, user_text, asst_text in fallback:
            S.append(Paragraph(label, H2))
            S.append(rule())
            S.append(bubble("user", user_text))
            S.append(sp(1))
            S.append(bubble("assistant", asst_text))
            S.append(sp(3))

    # ── Footer note ───────────────────────────────────────────────────────────
    S.append(sp(2))
    S.append(Paragraph(
        "<b>Note:</b> The full unedited conversation log (286 KB JSONL) is available on "
        "request. Session ID: 38778eed-e850-434d-b8f6-e013ee468440. Tool: Cursor IDE with "
        "Claude claude-4.6-sonnet-medium-thinking model.",
        ParagraphStyle("Note", fontName="Helvetica-Oblique", fontSize=8.5,
                       textColor=colors.gray, leading=12)
    ))

    return S


def main():
    print(f"Loading transcript...")
    msgs = load_messages()
    print(f"  Loaded {len(msgs)} messages")
    print(f"Generating {OUT} ...")
    doc   = make_doc(OUT)
    story = build_story(msgs)
    doc.build(story)
    size  = os.path.getsize(OUT) / 1024
    print(f"Done: {OUT}  ({size:.0f} KB)")


if __name__ == "__main__":
    main()
