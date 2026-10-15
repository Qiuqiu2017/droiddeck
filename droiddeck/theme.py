"""Visual styling for DroidDeck — a clean, modern, Material-inspired theme."""

from __future__ import annotations

# Palette
BG = "#0f1115"
SURFACE = "#171a21"
SURFACE_2 = "#1e2230"
BORDER = "#2a2f3a"
TEXT = "#e8eaf0"
TEXT_DIM = "#9aa2b1"
ACCENT = "#3ddc84"        # Android green
ACCENT_DARK = "#2bb673"
INFO = "#4c8dff"
WARN = "#ffb020"
DANGER = "#ff5c5c"

# CJK-capable families first: if a Latin-only family (e.g. Inter) is listed
# first and missing, Qt falls back per-glyph and bold CJK text gets odd
# letter-spacing. Keeping a CJK family first renders everything cleanly.
FONT_FAMILY = ("'Noto Sans CJK SC', 'Source Han Sans SC', 'WenQuanYi Micro Hei', "
               "'PingFang SC', 'Microsoft YaHei', 'Inter', 'DejaVu Sans', sans-serif")


def stylesheet() -> str:
    return f"""
    * {{
        font-family: {FONT_FAMILY};
        color: {TEXT};
        font-size: 14px;
        outline: none;
    }}
    QWidget#Root {{
        background: {BG};
    }}

    /* -------- sidebar -------- */
    QWidget#Sidebar {{
        background: {SURFACE};
        border-right: 1px solid {BORDER};
    }}
    QLabel#Brand {{
        font-size: 20px;
        font-weight: 800;
        color: {TEXT};
    }}
    QLabel#BrandSub {{
        color: {TEXT_DIM};
        font-size: 11px;
    }}
    QPushButton#Nav {{
        text-align: left;
        padding: 10px 14px;
        border-radius: 10px;
        color: {TEXT_DIM};
        background: transparent;
        font-weight: 600;
    }}
    QPushButton#Nav:hover {{
        background: {SURFACE_2};
        color: {TEXT};
    }}
    QPushButton#Nav:checked {{
        background: {SURFACE_2};
        color: {ACCENT};
    }}

    /* -------- cards -------- */
    QFrame#Card {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 16px;
    }}
    QFrame#Banner {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-left: 4px solid {INFO};
        border-radius: 14px;
    }}
    QLabel#H1 {{ font-size: 24px; font-weight: 800; }}
    QLabel#H2 {{ font-size: 16px; font-weight: 700; }}
    QLabel#Dim {{ color: {TEXT_DIM}; }}
    QLabel#DimSmall {{ color: {TEXT_DIM}; font-size: 12px; }}

    /* -------- buttons -------- */
    QPushButton#Primary {{
        background: {ACCENT};
        color: #06210f;
        font-weight: 700;
        border: none;
        border-radius: 12px;
        padding: 12px 20px;
    }}
    QPushButton#Primary:hover {{ background: #4cec92; }}
    QPushButton#Primary:pressed {{ background: {ACCENT_DARK}; }}
    QPushButton#Primary:disabled {{ background: {BORDER}; color: {TEXT_DIM}; }}

    QPushButton#Secondary {{
        background: {SURFACE_2};
        color: {TEXT};
        font-weight: 600;
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 12px 20px;
    }}
    QPushButton#Secondary:hover {{ border-color: {ACCENT}; }}
    QPushButton#Secondary:disabled {{
        color: {TEXT_DIM};
        background: {BG};
        border-color: {BORDER};
    }}

    QPushButton#Ghost {{
        background: transparent;
        color: {TEXT_DIM};
        border: none;
        padding: 6px 10px;
    }}
    QPushButton#Ghost:hover {{ color: {TEXT}; }}
    QPushButton#Ghost:checked {{
        color: {ACCENT};
        background: rgba(61,220,132,0.14);
        border: 1px solid {ACCENT};
        border-radius: 8px;
    }}

    QCheckBox:disabled {{ color: {TEXT_DIM}; }}

    /* -------- chips -------- */
    QLabel#Chip {{
        border-radius: 11px;
        padding: 3px 12px;
        font-size: 12px;
        font-weight: 700;
    }}
    QLabel#ChipRun {{ background: rgba(61,220,132,0.15); color: {ACCENT}; }}
    QLabel#ChipStop {{ background: rgba(255,92,92,0.15); color: {DANGER}; }}
    QLabel#ChipWarn {{ background: rgba(255,176,32,0.15); color: {WARN}; }}

    /* -------- app tiles -------- */
    QFrame#AppTile {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 16px;
    }}
    QFrame#AppTile:hover {{
        border-color: {ACCENT};
        background: {SURFACE_2};
    }}
    QLabel#AppName {{ font-weight: 700; }}
    QLabel#AppPkg {{ color: {TEXT_DIM}; font-size: 11px; }}

    /* -------- progress -------- */
    QProgressBar {{
        background: {SURFACE_2};
        border: none;
        border-radius: 6px;
        height: 8px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: {ACCENT};
        border-radius: 6px;
    }}

    /* -------- scroll -------- */
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: #3a4150; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

    /* -------- dialog (Android installer) -------- */
    QDialog {{ background: {SURFACE}; }}
    QWidget#InstallerRoot {{ background: {SURFACE}; border-radius: 20px; }}
    QLabel#InstallerTitle {{ font-size: 20px; font-weight: 800; }}
    QLabel#InstallerPkg {{ color: {TEXT_DIM}; font-size: 12px; }}
    """
