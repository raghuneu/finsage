"""
FinSage Report Agent
====================
Assembles validated charts + Cortex analyses into a professional
branded PDF report using reportlab.

Design: Option B — Midnight Teal
    Header/Footer:  #0f2027  (near black)
    Accent:         #00b4d8  (electric teal)
    Signal BULLISH: #06d6a0  (mint green)
    Signal BEARISH: #ef476f  (coral red)
    Signal NEUTRAL: #94a3b8  (slate)

PDF Structure:
    Page 1  — Cover page
    Page 2  — Executive Summary + key metrics table
    Pages 3-8 — One section per chart + analysis paragraph
    Page 9  — Risk Factors summary
    Page 10 — Appendix + data sources + disclaimer

Usage:
    Called by orchestrator.py — not run standalone in production.
    Dev test: python agents/report_agent.py
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable
)
from reportlab.platypus.flowables import KeepTogether

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Midnight Teal Palette
# ──────────────────────────────────────────────────────────────
C_DARK       = colors.HexColor("#0f2027")   # header / footer bg
C_TEAL       = colors.HexColor("#00b4d8")   # accent / section headers
C_TEAL_LIGHT = colors.HexColor("#e0f7fa")   # subtle teal background
C_BULLISH    = colors.HexColor("#06d6a0")   # BULLISH badge
C_BEARISH    = colors.HexColor("#ef476f")   # BEARISH badge
C_NEUTRAL    = colors.HexColor("#94a3b8")   # NEUTRAL badge
C_WHITE      = colors.white
C_BLACK      = colors.HexColor("#0f172a")
C_GRAY       = colors.HexColor("#64748b")
C_LIGHT_GRAY = colors.HexColor("#f1f5f9")
C_DIVIDER    = colors.HexColor("#e2e8f0")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"


# ──────────────────────────────────────────────────────────────
# Signal helpers
# ──────────────────────────────────────────────────────────────

def get_signal(chart_id: str, data_summary: dict) -> tuple:
    """
    Derive a BULLISH / BEARISH / NEUTRAL signal from chart data_summary.
    Returns (label, color).
    """
    if chart_id == "price_sma":
        sig = data_summary.get("trend_signal", "NEUTRAL")
        if "BULL" in sig:
            return "BULLISH ▲", C_BULLISH
        elif "BEAR" in sig:
            return "BEARISH ▼", C_BEARISH
        return "NEUTRAL →", C_NEUTRAL

    elif chart_id == "volatility":
        vol = data_summary.get("volatility_30d_pct", 0)
        if vol < 1.5:
            return "LOW VOL ▲", C_BULLISH
        elif vol > 3.0:
            return "HIGH VOL ▼", C_BEARISH
        return "MOD VOL →", C_NEUTRAL

    elif chart_id in ("revenue_growth", "eps_trend"):
        sig = data_summary.get("fundamental_signal",
              data_summary.get("eps_growth_yoy_pct", 0))
        if isinstance(sig, str):
            if "STRONG" in sig or "MODERATE" in sig:
                return "GROWTH ▲", C_BULLISH
            elif "DECLIN" in sig:
                return "DECLINING ▼", C_BEARISH
            return "MIXED →", C_NEUTRAL
        return ("GROWTH ▲", C_BULLISH) if float(sig) > 0 else ("DECLINING ▼", C_BEARISH)

    elif chart_id == "sentiment":
        label = data_summary.get("sentiment_label", "NEUTRAL")
        if "BULL" in label:
            return "BULLISH ▲", C_BULLISH
        elif "BEAR" in label:
            return "BEARISH ▼", C_BEARISH
        return "NEUTRAL →", C_NEUTRAL

    elif chart_id == "financial_health":
        health = data_summary.get("financial_health", "FAIR")
        if health in ("EXCELLENT", "HEALTHY"):
            return "HEALTHY ▲", C_BULLISH
        elif health == "UNPROFITABLE":
            return "WEAK ▼", C_BEARISH
        return "FAIR →", C_NEUTRAL

    return "NEUTRAL →", C_NEUTRAL


def overall_signal(charts: list) -> tuple:
    """Derive overall report signal from all chart signals."""
    bullish = 0
    bearish = 0
    for c in charts:
        label, _ = get_signal(c["chart_id"], c.get("data_summary", {}))
        if "▲" in label:
            bullish += 1
        elif "▼" in label:
            bearish += 1
    if bullish > bearish + 1:
        return "BULLISH ▲", C_BULLISH
    elif bearish > bullish + 1:
        return "BEARISH ▼", C_BEARISH
    return "NEUTRAL →", C_NEUTRAL


# ──────────────────────────────────────────────────────────────
# Styles
# ──────────────────────────────────────────────────────────────

def build_styles():
    base = getSampleStyleSheet()

    styles = {
        "cover_ticker": ParagraphStyle(
            "cover_ticker",
            fontName="Helvetica-Bold",
            fontSize=42,
            textColor=C_WHITE,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "cover_company": ParagraphStyle(
            "cover_company",
            fontName="Helvetica",
            fontSize=18,
            textColor=C_TEAL,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle",
            fontName="Helvetica",
            fontSize=13,
            textColor=C_WHITE,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "cover_date": ParagraphStyle(
            "cover_date",
            fontName="Helvetica",
            fontSize=11,
            textColor=C_NEUTRAL,
            alignment=TA_CENTER,
        ),
        "section_header": ParagraphStyle(
            "section_header",
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=C_WHITE,
            alignment=TA_LEFT,
            leftIndent=6,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=10,
            textColor=C_BLACK,
            alignment=TA_JUSTIFY,
            leading=16,
            spaceAfter=8,
        ),
        "exec_label": ParagraphStyle(
            "exec_label",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=C_GRAY,
            alignment=TA_LEFT,
        ),
        "exec_value": ParagraphStyle(
            "exec_value",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=C_BLACK,
            alignment=TA_LEFT,
        ),
        "disclaimer": ParagraphStyle(
            "disclaimer",
            fontName="Helvetica",
            fontSize=7.5,
            textColor=C_GRAY,
            alignment=TA_JUSTIFY,
            leading=11,
        ),
        "appendix_header": ParagraphStyle(
            "appendix_header",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=C_TEAL,
            spaceAfter=6,
        ),
        "appendix_body": ParagraphStyle(
            "appendix_body",
            fontName="Helvetica",
            fontSize=9,
            textColor=C_GRAY,
            leading=14,
        ),
        "risk_body": ParagraphStyle(
            "risk_body",
            fontName="Helvetica",
            fontSize=10,
            textColor=C_BLACK,
            alignment=TA_JUSTIFY,
            leading=16,
            spaceAfter=8,
        ),
        "page_title": ParagraphStyle(
            "page_title",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=C_DARK,
            spaceAfter=12,
        ),
    }
    return styles


# ──────────────────────────────────────────────────────────────
# Page templates — header/footer canvas callbacks
# ──────────────────────────────────────────────────────────────

def draw_cover_bg(canvas, doc):
    """Full dark background for cover page."""
    canvas.saveState()
    canvas.setFillColor(C_DARK)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Teal accent band
    canvas.setFillColor(C_TEAL)
    canvas.rect(0, PAGE_H * 0.38, PAGE_W, 3, fill=1, stroke=0)
    canvas.rect(0, PAGE_H * 0.36, PAGE_W, 1, fill=1, stroke=0)

    # Bottom footer bar
    canvas.setFillColor(colors.HexColor("#091318"))
    canvas.rect(0, 0, PAGE_W, 22 * mm, fill=1, stroke=0)

    # Footer text
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(C_NEUTRAL)
    canvas.drawString(MARGIN, 8 * mm, "FinSage — AI-Powered Financial Research")
    canvas.drawRightString(
        PAGE_W - MARGIN, 8 * mm,
        f"Generated {datetime.now().strftime('%B %d, %Y')}"
    )
    canvas.restoreState()


def draw_content_page(canvas, doc):
    """Header + footer for all content pages."""
    canvas.saveState()

    # ── Header bar ──────────────────────────────────────────
    canvas.setFillColor(C_DARK)
    canvas.rect(0, PAGE_H - 14 * mm, PAGE_W, 14 * mm, fill=1, stroke=0)

    # Teal accent line under header
    canvas.setFillColor(C_TEAL)
    canvas.rect(0, PAGE_H - 14 * mm - 1.5, PAGE_W, 2, fill=1, stroke=0)

    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(C_WHITE)
    canvas.drawString(MARGIN, PAGE_H - 9 * mm, "FinSage")

    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(C_TEAL)
    ticker = getattr(doc, "_finsage_ticker", "")
    canvas.drawString(MARGIN + 38, PAGE_H - 9 * mm, f"| {ticker} Equity Research Report")

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(C_NEUTRAL)
    canvas.drawRightString(
        PAGE_W - MARGIN, PAGE_H - 9 * mm,
        datetime.now().strftime("%B %d, %Y")
    )

    # ── Footer bar ──────────────────────────────────────────
    canvas.setFillColor(C_DARK)
    canvas.rect(0, 0, PAGE_W, 12 * mm, fill=1, stroke=0)

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(C_NEUTRAL)
    canvas.drawString(MARGIN, 4 * mm, "Confidential — For Internal Use Only")
    canvas.drawRightString(
        PAGE_W - MARGIN, 4 * mm,
        f"Page {doc.page}"
    )

    # Teal accent line above footer
    canvas.setFillColor(C_TEAL)
    canvas.rect(0, 12 * mm, PAGE_W, 1.5, fill=1, stroke=0)

    canvas.restoreState()


# ──────────────────────────────────────────────────────────────
# Flowable builders
# ──────────────────────────────────────────────────────────────

def build_cover(ticker: str, company_name: str, styles: dict,
                overall_sig: tuple) -> list:
    """Build cover page elements."""
    sig_label, sig_color = overall_sig
    elements = []

    elements.append(Spacer(1, 52 * mm))

    # FinSage wordmark
    elements.append(Paragraph(
        '<font color="#00b4d8" size="11"><b>FinSage</b></font>'
        '<font color="#94a3b8" size="9">  |  AI-Powered Financial Research</font>',
        ParagraphStyle("wm", fontName="Helvetica", fontSize=11,
                       textColor=C_WHITE, alignment=TA_CENTER)
    ))
    elements.append(Spacer(1, 10 * mm))

    # Ticker
    elements.append(Paragraph(ticker, styles["cover_ticker"]))

    # Company name
    elements.append(Paragraph(company_name, styles["cover_company"]))
    elements.append(Spacer(1, 6 * mm))

    # Report type
    elements.append(Paragraph(
        "EQUITY RESEARCH REPORT", styles["cover_subtitle"]
    ))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        datetime.now().strftime("%B %d, %Y"), styles["cover_date"]
    ))

    elements.append(Spacer(1, 14 * mm))

    # Overall signal badge
    sig_hex = sig_color.hexval() if hasattr(sig_color, "hexval") else "#94a3b8"
    elements.append(Paragraph(
        f'<font color="{sig_hex}" size="13"><b>{sig_label}</b></font>',
        ParagraphStyle("sig", fontName="Helvetica-Bold", fontSize=13,
                       textColor=C_WHITE, alignment=TA_CENTER)
    ))

    elements.append(PageBreak())
    return elements


def build_executive_summary(ticker: str, charts: list,
                             analysis: dict, styles: dict) -> list:
    """Build executive summary page with key metrics grid."""
    elements = []
    elements.append(Paragraph("Executive Summary", styles["page_title"]))
    elements.append(HRFlowable(
        width="100%", thickness=1.5,
        color=C_TEAL, spaceAfter=10
    ))

    # Key metrics table — pull from data_summaries
    chart_map = {c["chart_id"]: c for c in charts}

    price_data = chart_map.get("price_sma", {}).get("data_summary", {})
    vol_data   = chart_map.get("volatility", {}).get("data_summary", {})
    fund_data  = chart_map.get("revenue_growth", {}).get("data_summary", {})
    eps_data   = chart_map.get("eps_trend", {}).get("data_summary", {})
    sent_data  = chart_map.get("sentiment", {}).get("data_summary", {})
    fin_data   = chart_map.get("financial_health", {}).get("data_summary", {})

    def metric_cell(label, value):
        return [
            Paragraph(label, styles["exec_label"]),
            Paragraph(str(value), styles["exec_value"]),
        ]

    metrics = [
        [
            metric_cell("Current Price",
                f"${price_data.get('current_price', 'N/A')}"),
            metric_cell("Trend Signal",
                price_data.get("trend_signal", "N/A")),
            metric_cell("30D Volatility",
                f"{vol_data.get('volatility_30d_pct', 'N/A')}%"),
        ],
        [
            metric_cell("Revenue Growth (YoY)",
                f"{fund_data.get('latest_revenue_growth_yoy', 'N/A')}%"),
            metric_cell("Latest EPS",
                f"${eps_data.get('latest_eps', 'N/A')}"),
            metric_cell("EPS Growth (YoY)",
                f"{eps_data.get('eps_growth_yoy_pct', 'N/A')}%"),
        ],
        [
            metric_cell("Net Margin",
                f"{fin_data.get('net_margin_pct', 'N/A')}%"),
            metric_cell("Debt/Equity",
                fin_data.get("debt_to_equity_ratio", "N/A")),
            metric_cell("News Sentiment",
                sent_data.get("sentiment_label", "N/A")),
        ],
    ]

    col_w = (PAGE_W - 2 * MARGIN) / 3

    for row in metrics:
        t = Table(
            [[cell for cell in row]],
            colWidths=[col_w, col_w, col_w]
        )
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT_GRAY),
            ("BOX",        (0, 0), (-1, -1), 0.5, C_DIVIDER),
            ("INNERGRID",  (0, 0), (-1, -1), 0.5, C_DIVIDER),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 2))

    elements.append(Spacer(1, 8 * mm))

    # MD&A summary paragraph
    elements.append(Paragraph(
        "Management Commentary Summary", styles["appendix_header"]
    ))
    elements.append(HRFlowable(
        width="100%", thickness=0.5,
        color=C_DIVIDER, spaceAfter=6
    ))
    mda = analysis.get("mda_summary", "Not available.")
    elements.append(Paragraph(mda, styles["body"]))

    elements.append(PageBreak())
    return elements


def build_chart_section(chart: dict, analysis_text: str,
                         styles: dict) -> list:
    """Build one chart section: teal header bar + chart image + analysis."""
    elements = []

    chart_id = chart["chart_id"]
    title = chart.get("title", chart_id)
    data_summary = chart.get("data_summary", {})
    sig_label, sig_color = get_signal(chart_id, data_summary)

    # ── Section header bar ───────────────────────────────────
    sig_hex = sig_color.hexval() if hasattr(sig_color, "hexval") else "#94a3b8"

    header_data = [[
        Paragraph(title, styles["section_header"]),
        Paragraph(
            f'<font color="{sig_hex}"><b>{sig_label}</b></font>',
            ParagraphStyle("badge", fontName="Helvetica-Bold",
                           fontSize=10, textColor=C_WHITE,
                           alignment=TA_CENTER)
        ),
    ]]

    content_width = PAGE_W - 2 * MARGIN
    header_table = Table(
        header_data,
        colWidths=[content_width * 0.75, content_width * 0.25]
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (0, 0),   10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (1, 0), (1, 0),   "CENTER"),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 4))

    # ── Chart image ──────────────────────────────────────────
    file_path = chart.get("file_path", "")
    if file_path and os.path.exists(file_path):
        img_width = content_width
        img_height = img_width * (6 / 14)  # preserve 14:6 aspect ratio
        img = Image(file_path, width=img_width, height=img_height)
        elements.append(img)
    else:
        elements.append(Paragraph(
            f"[Chart image not available: {file_path}]",
            styles["body"]
        ))

    elements.append(Spacer(1, 5))

    # ── Teal accent line ─────────────────────────────────────
    elements.append(HRFlowable(
        width="100%", thickness=1,
        color=C_TEAL, spaceAfter=6
    ))

    # ── Analysis paragraph ───────────────────────────────────
    elements.append(Paragraph(analysis_text, styles["body"]))
    elements.append(Spacer(1, 6 * mm))

    return elements


def build_risk_section(risk_summary: str, styles: dict) -> list:
    """Build risk factors page."""
    elements = []
    elements.append(PageBreak())
    elements.append(Paragraph("Risk Factors", styles["page_title"]))
    elements.append(HRFlowable(
        width="100%", thickness=1.5,
        color=C_BEARISH, spaceAfter=10
    ))

    # Risk header bar
    risk_header = Table(
        [[Paragraph("Key Risk Considerations", styles["section_header"])]],
        colWidths=[PAGE_W - 2 * MARGIN]
    )
    risk_header.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
    ]))
    elements.append(risk_header)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(risk_summary, styles["risk_body"]))
    return elements


def build_appendix(ticker: str, charts: list, styles: dict) -> list:
    """Build appendix + disclaimer page."""
    elements = []
    elements.append(PageBreak())
    elements.append(Paragraph("Appendix & Data Sources", styles["page_title"]))
    elements.append(HRFlowable(
        width="100%", thickness=1.5,
        color=C_TEAL, spaceAfter=10
    ))

    # Data sources table
    elements.append(Paragraph("Data Sources", styles["appendix_header"]))
    sources = [
        ["Source", "Data Type", "Layer"],
        ["Yahoo Finance", "OHLCV Price Data, Fundamentals", "RAW → STAGING → ANALYTICS"],
        ["NewsAPI", "Financial News Articles", "RAW → STAGING → ANALYTICS"],
        ["SEC EDGAR (XBRL)", "Financial Statement Concepts", "RAW → STAGING → ANALYTICS"],
        ["SEC EDGAR (HTML)", "10-K/10-Q Filing Text", "RAW (S3)"],
        ["Snowflake Cortex", "LLM Analysis & Summarization", "CAVM Pipeline"],
    ]

    content_width = PAGE_W - 2 * MARGIN
    src_table = Table(
        sources,
        colWidths=[content_width * 0.25, content_width * 0.45, content_width * 0.30]
    )
    src_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_DARK),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("BACKGROUND",    (0, 1), (-1, -1), C_LIGHT_GRAY),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_LIGHT_GRAY, C_WHITE]),
        ("GRID",          (0, 0), (-1, -1), 0.5, C_DIVIDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    elements.append(src_table)
    elements.append(Spacer(1, 8 * mm))

    # Chart generation metadata
    elements.append(Paragraph("Chart Generation Metadata", styles["appendix_header"]))
    chart_meta = [["Chart", "Method", "Refinement Iterations", "Validated"]]
    for c in charts:
        method = "LLM + VLM Refinement" if c.get("refinement_count", 0) > 0 else "Fallback"
        chart_meta.append([
            c.get("title", c["chart_id"]),
            method,
            str(c.get("refinement_count", 0)),
            "✓" if c.get("validated") else "✗",
        ])

    meta_table = Table(
        chart_meta,
        colWidths=[content_width * 0.35, content_width * 0.35,
                   content_width * 0.18, content_width * 0.12]
    )
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_DARK),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_LIGHT_GRAY, C_WHITE]),
        ("GRID",          (0, 0), (-1, -1), 0.5, C_DIVIDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("ALIGN",         (2, 0), (-1, -1), "CENTER"),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10 * mm))

    # Disclaimer
    elements.append(HRFlowable(
        width="100%", thickness=0.5,
        color=C_DIVIDER, spaceAfter=6
    ))
    elements.append(Paragraph(
        "DISCLAIMER",
        ParagraphStyle("disc_hdr", fontName="Helvetica-Bold",
                       fontSize=8, textColor=C_GRAY, spaceAfter=4)
    ))
    elements.append(Paragraph(
        f"This report was generated automatically by FinSage, an AI-powered financial research "
        f"system developed at Northeastern University (DAMG 7374). The information contained "
        f"herein is derived from publicly available data sources including Yahoo Finance, "
        f"NewsAPI, and SEC EDGAR. This report does not constitute financial advice, investment "
        f"recommendations, or an offer to buy or sell any security. All data is provided for "
        f"informational and educational purposes only. FinSage and its authors make no "
        f"representations or warranties regarding the accuracy, completeness, or timeliness "
        f"of the information contained in this report. Past performance is not indicative of "
        f"future results. Generated on {datetime.now().strftime('%B %d, %Y at %H:%M UTC')}.",
        styles["disclaimer"]
    ))

    return elements


# ──────────────────────────────────────────────────────────────
# Main PDF builder
# ──────────────────────────────────────────────────────────────

def build_pdf(
    ticker: str,
    charts: list,
    analysis: dict,
    output_path: str,
    company_name: str = None,
) -> str:
    """
    Assemble the full FinSage PDF report.

    Args:
        ticker:       Stock ticker symbol
        charts:       List of ChartResult dicts from chart_agent/validation_agent
        analysis:     Dict from analysis_agent:
                        {chart_analyses: [...], mda_summary: str, risk_summary: str}
        output_path:  Full path for output PDF file
        company_name: Optional display name (defaults to ticker)

    Returns:
        output_path (str)
    """
    company_name = company_name or ticker
    styles = build_styles()

    # Build analysis lookup
    analysis_map = {
        a["chart_id"]: a["analysis_text"]
        for a in analysis.get("chart_analyses", [])
    }

    # Overall signal for cover
    sig = overall_signal(charts)

    # ── Doc setup ────────────────────────────────────────────
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
        title=f"FinSage — {ticker} Equity Research Report",
        author="FinSage AI",
        subject=f"{ticker} Financial Analysis",
    )
    doc._finsage_ticker = ticker  # used by header callback

    # ── Page templates ───────────────────────────────────────
    cover_frame = Frame(
        0, 0, PAGE_W, PAGE_H,
        leftPadding=MARGIN, rightPadding=MARGIN,
        topPadding=0, bottomPadding=0,
        id="cover"
    )
    content_frame = Frame(
        MARGIN, 14 * mm,
        PAGE_W - 2 * MARGIN, PAGE_H - 28 * mm,
        id="content"
    )

    doc.addPageTemplates([
        PageTemplate(id="Cover",   frames=[cover_frame],
                     onPage=draw_cover_bg),
        PageTemplate(id="Content", frames=[content_frame],
                     onPage=draw_content_page),
    ])

    # ── Assemble elements ────────────────────────────────────
    elements = []

    # Cover
    elements.append(NextPageTemplate("Cover"))
    elements += build_cover(ticker, company_name, styles, sig)

    # Switch to content template
    elements.append(NextPageTemplate("Content"))

    # Executive summary
    elements += build_executive_summary(ticker, charts, analysis, styles)

    # Chart sections
    elements.append(Paragraph("Analysis Sections", styles["page_title"]))
    elements.append(HRFlowable(
        width="100%", thickness=1.5,
        color=C_TEAL, spaceAfter=12
    ))

    for chart in charts:
        chart_id = chart["chart_id"]
        analysis_text = analysis_map.get(
            chart_id,
            "Analysis not available for this chart."
        )
        section = build_chart_section(chart, analysis_text, styles)
        elements.append(KeepTogether(section[:3]))  # keep header+chart together
        elements += section[3:]                     # analysis can flow freely

    # Risk factors
    elements += build_risk_section(
        analysis.get("risk_summary", "Risk factors not available."),
        styles
    )

    # Appendix
    elements += build_appendix(ticker, charts, styles)

    # ── Build PDF ────────────────────────────────────────────
    logger.info("Building PDF: %s", output_path)
    doc.build(elements)
    file_size = os.path.getsize(output_path)
    logger.info("✅ PDF complete: %s (%.1f KB)", output_path, file_size / 1024)

    return output_path


# ──────────────────────────────────────────────────────────────
# Main entry point (called by orchestrator)
# ──────────────────────────────────────────────────────────────

def generate_report(
    ticker: str,
    charts: list,
    analysis: dict,
    output_dir: str = None,
    company_name: str = None,
) -> str:
    """
    Generate the FinSage PDF report.

    Args:
        ticker:      Stock ticker symbol
        charts:      Validated ChartResult list from chart_agent
        analysis:    Output from analysis_agent.run_analysis()
        output_dir:  Directory to save PDF (defaults to outputs/)
        company_name: Display name for cover page

    Returns:
        Full path to generated PDF
    """
    if output_dir is None:
        output_dir = str(OUTPUT_DIR)

    os.makedirs(output_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ticker}_FinSage_Report_{date_str}.pdf"
    output_path = os.path.join(output_dir, filename)

    logger.info("═" * 50)
    logger.info("Report Agent starting for %s", ticker)
    logger.info("Output: %s", output_path)
    logger.info("═" * 50)

    return build_pdf(
        ticker=ticker,
        charts=charts,
        analysis=analysis,
        output_path=output_path,
        company_name=company_name,
    )


# ──────────────────────────────────────────────────────────────
# Dev test
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import glob
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

    from snowflake_connection import get_session
    import json

    # Load real charts from most recent chart_agent run
    output_folders = sorted(
        glob.glob(str(OUTPUT_DIR / "AAPL_*")),
        reverse=True
    )

    charts_to_use = []
    latest = None
    for folder in output_folders:
        manifest_path = os.path.join(folder, "chart_manifest.json")
        if os.path.exists(manifest_path):
            latest = folder
            with open(manifest_path) as f:
                manifest = json.load(f)
            # Re-attach file_paths (not stored in manifest)
            for entry in manifest:
                entry["file_path"] = os.path.join(folder, f"{entry['chart_id']}.png")
            charts_to_use = manifest
            break

    if not charts_to_use:
        print("❌ No chart output found — run chart_agent.py first")
        sys.exit(1)

    print(f"✅ Using real charts from: {latest}")
    print(f"   {len(charts_to_use)} charts loaded")

    # Run analysis agent with real Cortex
    session = get_session()

    from agents.analysis_agent import run_analysis
    analysis = run_analysis(session, charts_to_use, "AAPL")
    session.close()

    # Generate report
    pdf_path = generate_report(
        ticker="AAPL",
        charts=charts_to_use,
        analysis=analysis,
        company_name="Apple Inc.",
    )

    print(f"\n✅ Report generated: {pdf_path}")
    print(f"   Open with: open \"{pdf_path}\"")
