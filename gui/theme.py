ACCENT = '#7c5cff'
ACCENT_HOVER = '#6a4bef'
SUCCESS = '#2dce89'
WARNING = '#ffb020'
ERROR = '#fb6360'
_DARK = {
    'bg': '#0f1115',
    'sidebar_bg': '#0a0b0e',
    'surface': '#181b22',
    'surface_alt': '#20242e',
    'border': '#2a2f3a',
    'text': '#e8e9ed',
    'text_muted': '#8a90a0',
    'log_bg': '#0d0e12',
}
_LIGHT = {
    'bg': '#f3f4f7',
    'sidebar_bg': '#ffffff',
    'surface': '#ffffff',
    'surface_alt': '#eef0f4',
    'border': '#e2e5eb',
    'text': '#171923',
    'text_muted': '#6b7280',
    'log_bg': '#ffffff',
}
_TEMPLATE = """
QMainWindow {{
    background-color: {bg};
}}

#Central {{
    background-color: {bg};
}}

QWidget {{
    background-color: transparent;
    color: {text};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 10pt;
}}

QLabel {{
    background-color: transparent;
}}

#Sidebar {{
    background-color: {sidebar_bg};
    border-right: 1px solid {border};
}}

QToolButton#SidebarBtn {{
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 10px;
}}

QToolButton#SidebarBtn:hover {{
    background-color: {surface_alt};
}}

QLabel#Title {{
    font-size: 19pt;
    font-weight: 700;
}}

QLabel#Subtitle {{
    color: {text_muted};
    font-size: 9.5pt;
}}

#DropZone {{
    background-color: {surface};
    border: 2px dashed {border};
    border-radius: 16px;
}}
#DropZone:hover {{
    border: 2px dashed %(accent)s;
}}
QLabel#DropTitle {{
    font-size: 12pt;
    font-weight: 600;
}}
QLabel#DropSubtitle {{
    color: {text_muted};
    font-size: 9pt;
}}
QLineEdit {{
    background-color: {surface_alt};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 9px 12px;
    font-family: "Consolas", monospace;
    selection-background-color: %(accent)s;
}}
QLineEdit:focus {{
    border: 1px solid %(accent)s;
}}
QPushButton {{
    background-color: {surface_alt};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px 16px;
}}
QPushButton:hover {{
    border: 1px solid %(accent)s;
}}
QPushButton:disabled {{
    color: {text_muted};
    border: 1px solid {border};
}}
QPushButton#PrimaryButton {{
    background-color: %(accent)s;
    border: 1px solid %(accent)s;
    color: white;
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{
    background-color: %(accent_hover)s;
}}
QPushButton#PrimaryButton:disabled {{
    background-color: {surface_alt};
    color: {text_muted};
    border: 1px solid {border};
}}
QLabel[chip="neutral"] {{
    background-color: {surface_alt};
    color: {text_muted};
    border-radius: 11px;
    padding: 5px 14px;
    font-weight: 600;
    font-size: 9pt;
}}
QLabel[chip="success"] {{
    background-color: rgba(45, 206, 137, 0.16);
    color: %(success)s;
    border-radius: 11px;
    padding: 5px 14px;
    font-weight: 600;
    font-size: 9pt;
}}
QLabel[chip="warning"] {{
    background-color: rgba(255, 176, 32, 0.16);
    color: %(warning)s;
    border-radius: 11px;
    padding: 5px 14px;
    font-weight: 600;
    font-size: 9pt;
}}
QLabel[chip="error"] {{
    background-color: rgba(251, 99, 96, 0.16);
    color: %(error)s;
    border-radius: 11px;
    padding: 5px 14px;
    font-weight: 600;
    font-size: 9pt;
}}
QTextEdit#LogView {{
    background-color: {log_bg};
    border: 1px solid {border};
    border-radius: 10px;
    font-family: "Consolas", monospace;
    font-size: 9.5pt;
    padding: 10px;
}}
QTreeWidget {{
    background-color: {log_bg};
    border: 1px solid {border};
    border-radius: 10px;
    alternate-background-color: {surface_alt};
}}
QTreeWidget::item {{
    padding: 3px;
}}
QHeaderView::section {{
    background-color: {surface_alt};
    border: none;
    border-bottom: 1px solid {border};
    padding: 6px;
    font-weight: 600;
}}
QTabWidget::pane {{
    border: none;
    margin-top: 8px;
}}
QTabBar::tab {{
    background: transparent;
    color: {text_muted};
    padding: 8px 18px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {text};
    border-bottom: 2px solid %(accent)s;
    font-weight: 600;
}}
QProgressBar {{
    background-color: {surface_alt};
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: %(accent)s;
    border-radius: 5px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {border};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QMenu {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 20px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background-color: %(accent)s;
    color: white;
}}
""" % {
    'accent': ACCENT,
    'accent_hover': ACCENT_HOVER,
    'success': SUCCESS,
    'warning': WARNING,
    'error': ERROR,
}
DARK_STYLESHEET = _TEMPLATE.format(**_DARK)
LIGHT_STYLESHEET = _TEMPLATE.format(**_LIGHT)