"""
Generate docs/api_documentation.pdf from the live OpenAPI spec.
Requires the FastAPI server to be running on port 8000.

Run:
    uvicorn app.main:app --port 8000 &
    python docs/generate_api_docs_pdf.py
"""

import json
import os
import urllib.request

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

OUT = os.path.join(os.path.dirname(__file__), "api_documentation.pdf")

# ── Colours ────────────────────────────────────────────────────────────────
BLUE  = colors.HexColor("#1e50a0")
LBLUE = colors.HexColor("#e6edff")
WHITE = colors.white
GRAY  = colors.HexColor("#f5f8ff")
BGRAY = colors.HexColor("#f0f0f0")

METHOD_COLORS = {
    "get":    colors.HexColor("#2e7d32"),
    "post":   colors.HexColor("#1565c0"),
    "put":    colors.HexColor("#e65100"),
    "delete": colors.HexColor("#b71c1c"),
    "patch":  colors.HexColor("#6a1b9a"),
}

# ── Paragraph styles ───────────────────────────────────────────────────────
TITLE  = ParagraphStyle("Title",  fontName="Helvetica-Bold",   fontSize=20, textColor=BLUE, spaceAfter=4, alignment=1)
SUB    = ParagraphStyle("Sub",    fontName="Helvetica",        fontSize=11, textColor=colors.HexColor("#555"), spaceAfter=10, alignment=1)
H1     = ParagraphStyle("H1",     fontName="Helvetica-Bold",   fontSize=12, textColor=WHITE, spaceBefore=8, spaceAfter=3, backColor=BLUE, leftIndent=-4, borderPad=4)
H2     = ParagraphStyle("H2",     fontName="Helvetica-Bold",   fontSize=10, textColor=BLUE, spaceBefore=6, spaceAfter=2)
BODY   = ParagraphStyle("Body",   fontName="Helvetica",        fontSize=9,  leading=13, spaceAfter=4)
SMALL  = ParagraphStyle("Small",  fontName="Helvetica",        fontSize=8.5,leading=12, spaceAfter=3)
CODE   = ParagraphStyle("Code",   fontName="Courier",          fontSize=8,  backColor=BGRAY, borderPad=3, leftIndent=6, spaceAfter=4)
THDR   = ParagraphStyle("TH",     fontName="Helvetica-Bold",   fontSize=8.5,textColor=colors.black)
TCELL  = ParagraphStyle("TD",     fontName="Helvetica",        fontSize=8.5,leading=11)
METH   = ParagraphStyle("Meth",   fontName="Helvetica-Bold",   fontSize=8,  textColor=WHITE)
PATH_S = ParagraphStyle("Path",   fontName="Courier-Bold",     fontSize=8.5,textColor=colors.black)
FOOT   = ParagraphStyle("Foot",   fontName="Helvetica-Oblique",fontSize=7.5,textColor=colors.gray, alignment=1)


def sp(n=3): return Spacer(1, n*mm)
def rule():  return HRFlowable(width="100%", thickness=0.4, color=colors.lightgrey, spaceAfter=1)

def grid(headers, rows, col_ws=None):
    data = [[Paragraph(h, THDR) for h in headers]]
    for r in rows:
        data.append([Paragraph(str(c or ""), TCELL) for c in r])
    style = TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), LBLUE),
        ("BOX",          (0,0), (-1,-1), 0.5, colors.HexColor("#b0c0e0")),
        ("INNERGRID",    (0,0), (-1,-1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",   (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0), (-1,-1), 3),
        ("LEFTPADDING",  (0,0), (-1,-1), 4),
    ])
    return Table(data, colWidths=col_ws, style=style, hAlign="LEFT")


def method_badge(method: str) -> Table:
    col = METHOD_COLORS.get(method.lower(), colors.gray)
    cell = Paragraph(f"<b>{method.upper()}</b>", METH)
    t = Table([[cell]], colWidths=[18*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), col),
        ("TOPPADDING",  (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
    ]))
    return t


def endpoint_row(method: str, path: str, summary: str, auth: bool) -> Table:
    badge   = method_badge(method)
    path_p  = Paragraph(f"<b>{path}</b>", PATH_S)
    sum_p   = Paragraph(summary or "", SMALL)
    lock    = Paragraph("<font color='#b71c1c'>&#128274; Auth required</font>", SMALL) if auth else Paragraph("", SMALL)

    inner = Table(
        [[path_p, sum_p, lock]],
        colWidths=[68*mm, 75*mm, 28*mm],
    )
    inner.setStyle(TableStyle([
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 2),
        ("BOTTOMPADDING",(0,0), (-1,-1), 2),
        ("LEFTPADDING",  (0,0), (-1,-1), 4),
    ]))

    outer = Table([[badge, inner]], colWidths=[20*mm, None])
    outer.setStyle(TableStyle([
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("BOX",          (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING",   (0,0), (-1,-1), 0),
        ("BOTTOMPADDING",(0,0), (-1,-1), 0),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
    ]))
    return outer


def schema_to_table(schema: dict, definitions: dict) -> Table | None:
    """Render a JSON schema object as a parameter table."""
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    if not props:
        return None
    rows = []
    for name, info in props.items():
        typ   = info.get("type", info.get("$ref", "").split("/")[-1] or "any")
        desc  = info.get("description", "")
        req   = "Yes" if name in required else ""
        rows.append([name, typ, req, desc[:90]])
    return grid(["Field", "Type", "Required", "Description"], rows,
                col_ws=[28*mm, 18*mm, 16*mm, 113*mm])


def make_doc(path):
    W, H = A4
    LM = RM = 18*mm; TM = 22*mm; BM = 18*mm

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Oblique", 7.5)
        canvas.setFillColor(colors.gray)
        canvas.drawRightString(W - RM, H - 13*mm, "Nutrition & Recipe Analytics API -- API Documentation")
        canvas.drawCentredString(W / 2, BM - 6*mm, f"Page {doc.page}")
        canvas.restoreState()

    frame = Frame(LM, BM, W - LM - RM, H - TM - BM, id="body")
    pt    = PageTemplate(id="main", frames=[frame], onPage=header_footer)
    doc   = BaseDocTemplate(path, pagesize=A4, pageTemplates=[pt])
    return doc


def fetch_spec(url="http://localhost:8000/openapi.json") -> dict:
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def build_story(spec: dict) -> list:
    S = []
    info  = spec.get("info", {})
    title = info.get("title", "API")
    ver   = info.get("version", "1.0")
    desc  = info.get("description", "")

    # ── Cover ────────────────────────────────────────────────────────────────
    S += [sp(8), Paragraph(title, TITLE),
          Paragraph(f"API Reference Documentation &nbsp;|&nbsp; v{ver}", SUB), sp(2)]

    # Strip markdown from description for clean text
    clean_desc = desc.replace("**", "").replace("##", "").replace("#", "").replace("*", "").strip()
    first_para = clean_desc.split("\n\n")[0][:400]
    S.append(Paragraph(first_para, BODY))
    S.append(sp(3))

    # Base info table
    servers = spec.get("servers", [])
    base_url = servers[0]["url"] if servers else "http://localhost:8000"
    S.append(grid(
        ["Property", "Value"],
        [
            ["Base URL",       base_url],
            ["OpenAPI",        "3.1.0"],
            ["Auth",           "JWT Bearer Token (OAuth2 Password Flow)"],
            ["Response format","application/json"],
            ["Swagger UI",     f"{base_url}/docs"],
            ["ReDoc",          f"{base_url}/redoc"],
        ],
        col_ws=[38*mm, 137*mm]
    ))
    S.append(sp(4))

    # ── Authentication ────────────────────────────────────────────────────────
    S += [Paragraph("Authentication", H1), sp(1)]
    S.append(Paragraph(
        "Protected endpoints require a Bearer token in the Authorization header. "
        "Obtain a token via POST /auth/login.", BODY
    ))
    S.append(grid(
        ["Step", "Endpoint", "Details"],
        [
            ["1. Register", "POST /auth/register", "JSON body: {username, email, password}. Returns user object."],
            ["2. Login",    "POST /auth/login",    "Form data: username, password. Returns {access_token, token_type}."],
            ["3. Use token","Authorization header", 'Add header: Authorization: Bearer <access_token>'],
        ],
        col_ws=[22*mm, 44*mm, 109*mm]
    ))
    S.append(sp(2))

    # ── Endpoints grouped by tag ──────────────────────────────────────────────
    tags_order = {}
    for path, methods in spec.get("paths", {}).items():
        for method, op in methods.items():
            if method in ("get","post","put","delete","patch"):
                for tag in op.get("tags", ["Other"]):
                    tags_order.setdefault(tag, []).append((method, path, op))

    schemas = spec.get("components", {}).get("schemas", {})

    for tag, endpoints in tags_order.items():
        S += [Paragraph(tag, H1), sp(1)]

        for method, path, op in endpoints:
            summary  = op.get("summary", "")
            desc_op  = (op.get("description") or "").strip().replace("\n", " ")[:200]
            security = bool(op.get("security"))

            # Endpoint header row
            S.append(endpoint_row(method, path, summary, security))

            if desc_op:
                S.append(Paragraph(desc_op, SMALL))

            # Query / path parameters
            params = op.get("parameters", [])
            if params:
                param_rows = []
                for p in params:
                    schema_p = p.get("schema", {})
                    typ      = schema_p.get("type", "string")
                    enum_v   = schema_p.get("enum", [])
                    default  = str(schema_p.get("default", ""))
                    desc_p   = p.get("description", "")[:80]
                    req_p    = "Yes" if p.get("required") else ""
                    in_p     = p.get("in", "")
                    display_type = f"{typ} [{','.join(str(e) for e in enum_v)}]" if enum_v else typ
                    param_rows.append([p["name"], in_p, display_type, req_p, default, desc_p])
                S.append(grid(
                    ["Parameter", "In", "Type", "Req", "Default", "Description"],
                    param_rows,
                    col_ws=[28*mm, 12*mm, 28*mm, 10*mm, 18*mm, 79*mm]
                ))

            # Request body
            rb = op.get("requestBody", {})
            if rb:
                content = rb.get("content", {})
                for ct, ct_val in content.items():
                    rb_schema = ct_val.get("schema", {})
                    ref = rb_schema.get("$ref", "")
                    if ref:
                        schema_name = ref.split("/")[-1]
                        rb_schema   = schemas.get(schema_name, rb_schema)
                    t = schema_to_table(rb_schema, schemas)
                    if t:
                        S.append(Paragraph(f"Request body ({ct}):", SMALL))
                        S.append(t)

            # Responses
            responses = op.get("responses", {})
            resp_rows = []
            for code, resp_info in responses.items():
                resp_desc = resp_info.get("description", "")[:80]
                resp_rows.append([code, resp_desc])
            if resp_rows:
                S.append(grid(
                    ["Status Code", "Description"],
                    resp_rows,
                    col_ws=[22*mm, 153*mm]
                ))

            S.append(sp(1))

        S.append(sp(2))

    # ── Error codes reference ─────────────────────────────────────────────────
    S += [Paragraph("Error Code Reference", H1), sp(1)]
    S.append(grid(
        ["Code", "Meaning", "When Returned"],
        [
            ["200 OK",                  "Success",                        "Successful GET / PUT"],
            ["201 Created",             "Resource created",               "Successful POST"],
            ["204 No Content",          "Success, no body",               "Successful DELETE"],
            ["400 Bad Request",         "Business logic error",           "Duplicate username, invalid filters"],
            ["401 Unauthorized",        "Missing or invalid JWT",         "Protected endpoint called without token"],
            ["403 Forbidden",           "Permission denied",              "Trying to modify a USDA ingredient"],
            ["404 Not Found",           "Resource does not exist",        "Ingredient/recipe ID not in database"],
            ["422 Unprocessable Entity","Validation error",               "Missing required field, wrong type"],
        ],
        col_ws=[32*mm, 38*mm, 105*mm]
    ))

    # ── MCP Tools reference ───────────────────────────────────────────────────
    S += [sp(2), Paragraph("MCP Server Tools (app/mcp_server.py)", H1), sp(1)]
    S.append(Paragraph(
        "The MCP server exposes 10 tools for AI assistant integration. "
        "Run with: python -m app.mcp_server", BODY
    ))
    S.append(grid(
        ["Tool", "Description"],
        [
            ["search_ingredients",        "Search USDA ingredients by name, returns nutrition per 100g"],
            ["get_ingredient_nutrition",  "Full nutrition profile + Nutrient Density Score (A-E grade)"],
            ["search_recipes",            "Search recipes with calorie/allergen/difficulty/time filters"],
            ["get_recipe_allergens",      "Allergen warnings with ingredient-level breakdown"],
            ["get_recipe_nutrition",      "Nutrition summary + DRI comparison, scalable by servings"],
            ["get_recipe_difficulty",     "Difficulty score 1-5 with factor breakdown"],
            ["check_allergens",           "Check a custom ingredient list for allergens"],
            ["get_analytics_summary",     "Database-wide stats: calorie distribution, top ingredients"],
            ["find_recipes_by_ingredients","Find recipes matching a list of available ingredients"],
            ["compare_ingredients",       "Side-by-side nutritional comparison of two ingredients"],
        ],
        col_ws=[52*mm, 123*mm]
    ))

    return S


def main():
    print("Fetching OpenAPI spec from http://localhost:8000/openapi.json ...")
    try:
        spec = fetch_spec()
    except Exception as e:
        print(f"ERROR: Could not fetch spec -- {e}")
        print("Make sure the server is running:  uvicorn app.main:app --port 8000")
        return

    print(f"Found {len(spec.get('paths', {}))} paths. Building PDF...")
    doc   = make_doc(OUT)
    story = build_story(spec)
    doc.build(story)
    size  = os.path.getsize(OUT) / 1024
    print(f"Done: {OUT}  ({size:.0f} KB)")


if __name__ == "__main__":
    main()
