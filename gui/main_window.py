import os
import qtawesome as qta
from PyQt6.QtCore import Qt, QUrl, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMenu, QProgressBar, QPushButton, QSizePolicy,
    QSpacerItem, QTabWidget, QTextEdit, QToolButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget
)
from core.pyinstaller_extractor import PyInstArchive
from core.nuitka_extractor import RUST_ACCEL_AVAILABLE, find_all_candidates
from gui.extraction_worker import ExtractionWorker
from gui.theme import ACCENT, DARK_STYLESHEET, ERROR, LIGHT_STYLESHEET, SUCCESS, WARNING
INFO_COLOR = '#8a90a0'
LOG_COLORS = {'success': SUCCESS, 'error': ERROR, 'warning': WARNING, 'info': INFO_COLOR}
PATH_ROLE = Qt.ItemDataRole.UserRole
class ClickableFrame(QFrame):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ExeMiner')
        self.resize(1080, 760)
        self.setMinimumSize(920, 620)
        self.setWindowIcon(qta.icon('fa5s.microchip', color=ACCENT))
        self.setAcceptDrops(True)
        self.is_dark = True
        self.worker = None
        self.extracted_path = None
        self.file_checked = False
        self._build_ui()
        self._apply_theme()
        if RUST_ACCEL_AVAILABLE:
            self._set_accel_chip('Rust accel: on', 'success')
            self.append_log('Rust acceleration enabled (exeminer_rust)', 'success')
        else:
            self._set_accel_chip('Rust accel: off', 'warning')
            self.append_log(
                'Rust acceleration not built - using the pure-Python scanner (see rust_ext/README.md)',
                'warning'
            )

    def _build_ui(self):
        central = QWidget()
        central.setObjectName('Central')
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_sidebar())
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 26, 30, 20)
        content_layout.setSpacing(16)
        content_layout.addLayout(self._build_header())
        content_layout.addWidget(self._build_drop_zone())
        content_layout.addWidget(self._build_path_row())
        content_layout.addWidget(self._build_actions_row())
        content_layout.addWidget(self._build_status_row())
        content_layout.addWidget(self._build_output_tabs(), stretch=1)
        content_layout.addWidget(self._build_footer())
        outer.addWidget(content, stretch=1)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName('Sidebar')
        sidebar.setFixedWidth(76)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 22, 0, 18)
        layout.setSpacing(0)
        logo = QLabel()
        logo.setPixmap(qta.icon('fa5s.microchip', color=ACCENT).pixmap(34, 34))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)
        layout.addStretch(1)
        self.pylingualBtn = QToolButton()
        self.pylingualBtn.setObjectName('SidebarBtn')
        self.pylingualBtn.setIcon(qta.icon('fa5s.magic', color=ACCENT))
        self.pylingualBtn.setIconSize(QSize(22, 22))
        self.pylingualBtn.setToolTip('Open Pylingual (decompile .pyc files)')
        self.pylingualBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pylingualBtn.clicked.connect(self.open_pylingual)
        layout.addWidget(self.pylingualBtn, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.themeBtn = QToolButton()
        self.themeBtn.setObjectName('SidebarBtn')
        self.themeBtn.setIcon(qta.icon('fa5s.sun', color=ACCENT))
        self.themeBtn.setIconSize(QSize(22, 22))
        self.themeBtn.setToolTip('Toggle light / dark theme')
        self.themeBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.themeBtn.clicked.connect(self.toggle_theme)
        layout.addWidget(self.themeBtn, alignment=Qt.AlignmentFlag.AlignHCenter)
        return sidebar

    def _build_header(self):
        row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel('ExeMiner')
        title.setObjectName('Title')
        title_col.addWidget(title)
        subtitle = QLabel('PyInstaller and Nuitka executable extractor')
        subtitle.setObjectName('Subtitle')
        title_col.addWidget(subtitle)
        row.addLayout(title_col)
        row.addStretch(1)
        self.accelChip = QLabel('Rust accel: off')
        self.accelChip.setProperty('chip', 'neutral')
        row.addWidget(self.accelChip, alignment=Qt.AlignmentFlag.AlignTop)
        return row

    def _build_drop_zone(self):
        zone = ClickableFrame()
        zone.setObjectName('DropZone')
        zone.setFixedHeight(140)
        zone.setCursor(Qt.CursorShape.PointingHandCursor)
        zone.clicked.connect(self.browse_file)
        layout = QVBoxLayout(zone)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa5s.file-upload', color=ACCENT).pixmap(36, 36))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        drop_title = QLabel('Drag and drop an executable here')
        drop_title.setObjectName('DropTitle')
        drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(drop_title)
        drop_subtitle = QLabel('or click to browse')
        drop_subtitle.setObjectName('DropSubtitle')
        drop_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(drop_subtitle)
        return zone

    def _build_path_row(self):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.pathEdit = QLineEdit()
        self.pathEdit.setPlaceholderText('No file selected')
        self.pathEdit.setReadOnly(False)
        layout.addWidget(self.pathEdit, stretch=1)
        self.browseBtn = QPushButton(' Browse')
        self.browseBtn.setIcon(qta.icon('fa5s.folder-open', color=ACCENT))
        self.browseBtn.clicked.connect(self.browse_file)
        layout.addWidget(self.browseBtn)
        return row

    def _build_actions_row(self):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.analyzeBtn = QPushButton(' Analyze')
        self.analyzeBtn.setIcon(qta.icon('fa5s.search', color=ACCENT))
        self.analyzeBtn.clicked.connect(self.check_file)
        layout.addWidget(self.analyzeBtn)
        self.extractBtn = QPushButton(' Extract')
        self.extractBtn.setObjectName('PrimaryButton')
        self.extractBtn.setIcon(qta.icon('fa5s.bolt', color='white'))
        self.extractBtn.clicked.connect(self.extract_file)
        layout.addWidget(self.extractBtn)
        layout.addStretch(1)
        self.openFolderBtn = QPushButton(' Open Folder')
        self.openFolderBtn.setIcon(qta.icon('fa5s.folder', color=ACCENT))
        self.openFolderBtn.setEnabled(False)
        self.openFolderBtn.clicked.connect(self.open_extracted_folder)
        layout.addWidget(self.openFolderBtn)
        self.clearBtn = QPushButton(' Clear')
        self.clearBtn.setIcon(qta.icon('fa5s.trash-alt', color=ACCENT))
        self.clearBtn.clicked.connect(self.clear_log)
        layout.addWidget(self.clearBtn)

        return row

    def _build_status_row(self):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)
        self.statusChip = QLabel('Ready')
        self.statusChip.setProperty('chip', 'neutral')
        layout.addWidget(self.statusChip)
        self.filesChip = QLabel('Files: 0')
        self.filesChip.setProperty('chip', 'neutral')
        layout.addWidget(self.filesChip)
        layout.addSpacerItem(QSpacerItem(16, 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.progressBar.setTextVisible(False)
        layout.addWidget(self.progressBar, stretch=1)
        self.progressLabel = QLabel('0%')
        self.progressLabel.setFixedWidth(38)
        layout.addWidget(self.progressLabel)
        return row

    def _build_output_tabs(self):
        self.tabs = QTabWidget()
        self.logView = QTextEdit()
        self.logView.setObjectName('LogView')
        self.logView.setReadOnly(True)
        self.logView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.logView.customContextMenuRequested.connect(self._show_log_menu)
        self.tabs.addTab(self.logView, 'Log')
        self.fileTree = QTreeWidget()
        self.fileTree.setHeaderLabels(['Name', 'Size', 'Type'])
        self.fileTree.setColumnWidth(0, 440)
        self.fileTree.setColumnWidth(1, 100)
        self.fileTree.setAlternatingRowColors(True)
        self.fileTree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.fileTree.customContextMenuRequested.connect(self._show_tree_menu)
        self.fileTree.itemDoubleClicked.connect(lambda item, col: self._open_item(item))
        self.tabs.addTab(self.fileTree, 'Extracted Files')
        return self.tabs

    def _build_footer(self):
        footer = QLabel('ExeMiner v1.0 - by Slay')
        footer.setObjectName('Subtitle')
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return footer

    def _restyle_chip(self, label):
        label.style().unpolish(label)
        label.style().polish(label)

    def _set_status_chip(self, text, kind='neutral'):
        self.statusChip.setText(text)
        self.statusChip.setProperty('chip', kind)
        self._restyle_chip(self.statusChip)

    def _set_files_chip(self, count):
        self.filesChip.setText(f'Files: {count}')
        self._restyle_chip(self.filesChip)

    def _set_accel_chip(self, text, kind):
        self.accelChip.setText(text)
        self.accelChip.setProperty('chip', kind)
        self._restyle_chip(self.accelChip)

    def _apply_theme(self):
        stylesheet = DARK_STYLESHEET if self.is_dark else LIGHT_STYLESHEET
        QApplication.instance().setStyleSheet(stylesheet)

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        self._apply_theme()
        icon_name = 'fa5s.sun' if self.is_dark else 'fa5s.moon'
        self.themeBtn.setIcon(qta.icon(icon_name, color=ACCENT))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if not path or not os.path.isfile(path):
            self.append_log(f'[!] Dropped item is not a file: {path}', 'warning')
            return
        self.pathEdit.setText(path)
        self.file_checked = False
        self._set_status_chip('File dropped', 'neutral')
        self.append_log(f'[+] File dropped: {path}', 'success')


    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Select Executable', '', 'Executable Files (*.exe);;All Files (*)'
        )
        if path:
            self.pathEdit.setText(path)
            self.file_checked = False
            self._set_status_chip('File selected', 'neutral')

    def append_log(self, msg, level='info'):
        color = LOG_COLORS.get(level, INFO_COLOR)
        cursor = self.logView.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = cursor.charFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(msg + '\n')
        self.logView.setTextCursor(cursor)
        self.logView.ensureCursorVisible()

    def clear_log(self):
        self.logView.clear()
        self.progressBar.setValue(0)
        self.progressLabel.setText('0%')
        self._set_files_chip(0)
        self._set_status_chip('Ready', 'neutral')
        self.append_log('Log cleared. Ready for new operation.', 'info')

    def _show_log_menu(self, pos):
        menu = QMenu(self)
        menu.addAction('Copy Selection', self._copy_log_selection)
        menu.addAction('Copy All', lambda: QApplication.clipboard().setText(self.logView.toPlainText()))
        menu.addSeparator()
        menu.addAction('Clear', self.clear_log)
        menu.exec(self.logView.mapToGlobal(pos))

    def _copy_log_selection(self):
        cursor = self.logView.textCursor()
        if cursor.hasSelection():
            QApplication.clipboard().setText(cursor.selectedText())

    def check_file(self):
        path = self.pathEdit.text().strip()
        if not path or not os.path.isfile(path):
            self.append_log('[!] Please select a valid file first', 'error')
            self._set_status_chip('No file selected', 'error')
            return

        self._set_status_chip('Analyzing...', 'warning')
        self.append_log('=' * 60, 'info')
        self.append_log('Starting file analysis...', 'info')

        try:
            with open(path, 'rb') as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                search_chunk = 65536
                found = False
                pos = size
                magic = PyInstArchive.MAGIC

                while pos > 0 and not found:
                    start = max(0, pos - search_chunk)
                    f.seek(start)
                    data = f.read(pos - start)
                    if magic in data:
                        found = True
                        break
                    pos = start

            if found:
                self.append_log('[+] PyInstaller archive detected', 'success')
                self._set_status_chip('Valid PyInstaller', 'success')
                self.file_checked = True
                return

        except Exception as e:
            self.append_log(f'[!] Error during PyInstaller analysis: {str(e)}', 'error')
            self._set_status_chip('Analysis failed', 'error')
            return

        self.append_log('No PyInstaller signature found. Checking for Nuitka...', 'info')

        try:
            candidates = find_all_candidates(path)
        except Exception as e:
            self.append_log(f'[!] Error during Nuitka analysis: {str(e)}', 'error')
            self._set_status_chip('Analysis failed', 'error')
            return

        if candidates:
            self.append_log(
                f'[+] Nuitka onefile signature detected ({len(candidates)} candidate offset(s))', 'success'
            )
            self._set_status_chip('Valid Nuitka onefile', 'success')
            self.file_checked = True
        else:
            self.append_log('[!] No PyInstaller or Nuitka signature found', 'warning')
            self.append_log('[!] This file may use an unsupported packer (e.g. cx_Freeze, py2exe)', 'warning')
            self._set_status_chip('Unrecognized format', 'warning')
            self.file_checked = False

    def extract_file(self):
        if self.worker is not None and self.worker.isRunning():
            self.append_log('[!] Extraction already in progress', 'warning')
            return

        path = self.pathEdit.text().strip()
        if not path or not os.path.isfile(path):
            self.append_log('[!] Please select a valid file first', 'error')
            self._set_status_chip('No file selected', 'error')
            return
        self.logView.clear()
        self.progressBar.setValue(0)
        self.progressLabel.setText('0%')
        self._set_status_chip('Extracting...', 'warning')
        self.extractBtn.setEnabled(False)
        self.analyzeBtn.setEnabled(False)
        self.browseBtn.setEnabled(False)
        self.append_log('=' * 60, 'info')
        self.append_log('Starting extraction process...', 'info')
        self.append_log('=' * 60, 'info')
        self.worker = ExtractionWorker(path)
        self.worker.log_message.connect(self.append_log)
        self.worker.progress_update.connect(self._on_progress)
        self.worker.file_count_known.connect(self._set_files_chip)
        self.worker.finished_extraction.connect(self._on_extraction_finished)
        self.worker.start()

    def _on_progress(self, done, total):
        pct = int((done / total) * 100) if total else 0
        self.progressBar.setValue(pct)
        self.progressLabel.setText(f'{pct}%')

    def _on_extraction_finished(self, success, extracted_dir):
        self.progressBar.setValue(100 if success else 0)

        if success:
            self._set_status_chip('Extraction complete', 'success')
            if extracted_dir:
                self.extracted_path = extracted_dir
                self.openFolderBtn.setEnabled(True)
                self._populate_file_tree(extracted_dir)
        else:
            self._set_status_chip('Extraction failed', 'error')

        self.extractBtn.setEnabled(True)
        self.analyzeBtn.setEnabled(True)
        self.browseBtn.setEnabled(True)

    def _populate_file_tree(self, root_dir):
        self.fileTree.clear()
        if not root_dir or not os.path.isdir(root_dir):
            return

        root_item = QTreeWidgetItem([os.path.basename(root_dir), '', 'folder'])
        root_item.setIcon(0, qta.icon('fa5s.folder', color=ACCENT))
        root_item.setData(0, PATH_ROLE, root_dir)
        self.fileTree.addTopLevelItem(root_item)
        self._insert_dir_children(root_item, root_dir)
        root_item.setExpanded(True)

    def _insert_dir_children(self, parent_item, dir_path):
        try:
            entries = sorted(
                os.listdir(dir_path),
                key=lambda n: (not os.path.isdir(os.path.join(dir_path, n)), n.lower())
            )
        except OSError as e:
            self.append_log(f'[!] Could not list {dir_path}: {e}', 'warning')
            return

        for name in entries:
            full_path = os.path.join(dir_path, name)
            if os.path.isdir(full_path):
                child = QTreeWidgetItem([name, '', 'folder'])
                child.setIcon(0, qta.icon('fa5s.folder', color=ACCENT))
                child.setData(0, PATH_ROLE, full_path)
                parent_item.addChild(child)
                self._insert_dir_children(child, full_path)
            else:
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = 0
                ext = os.path.splitext(name)[1].lstrip('.').upper() or 'FILE'
                child = QTreeWidgetItem([name, self._format_size(size), ext])
                child.setIcon(0, qta.icon('fa5.file', color=INFO_COLOR))
                child.setData(0, PATH_ROLE, full_path)
                parent_item.addChild(child)

    @staticmethod
    def _format_size(num_bytes):
        size = float(num_bytes)
        for unit in ('B', 'KB', 'MB', 'GB'):
            if size < 1024 or unit == 'GB':
                return f'{size:.0f} {unit}' if unit == 'B' else f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} TB'

    def _show_tree_menu(self, pos):
        item = self.fileTree.itemAt(pos)
        if item is None:
            return
        self.fileTree.setCurrentItem(item)
        path = item.data(0, PATH_ROLE) or ''

        menu = QMenu(self)
        menu.addAction('Open File', lambda: self._open_item(item, files_only=True))
        menu.addAction('Open Containing Folder', lambda: self._open_containing_folder(item))
        menu.addSeparator()
        menu.addAction('Copy Path', lambda: self._copy_path(item))

        if path.lower().endswith('.pyc'):
            menu.addSeparator()
            menu.addAction(
                qta.icon('fa5s.magic', color=ACCENT), 'Decompile with Pylingual', self.open_pylingual
            )

        menu.exec(self.fileTree.viewport().mapToGlobal(pos))

    def _open_item(self, item, files_only=False):
        path = item.data(0, PATH_ROLE)
        if not path:
            return
        if files_only and not os.path.isfile(path):
            self.append_log('[!] Select a file (not a folder) to open', 'warning')
            return
        if QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            self.append_log(f'[+] Opened: {path}', 'success')
        else:
            self.append_log(f'[!] Could not open: {path}', 'error')

    def _open_containing_folder(self, item):
        path = item.data(0, PATH_ROLE)
        if not path:
            return
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        if QDesktopServices.openUrl(QUrl.fromLocalFile(folder)):
            self.append_log(f'[+] Opened folder: {folder}', 'success')
        else:
            self.append_log(f'[!] Could not open: {folder}', 'error')

    def _copy_path(self, item):
        path = item.data(0, PATH_ROLE)
        if not path:
            return
        QApplication.clipboard().setText(path)
        self.append_log(f'[+] Path copied: {path}', 'success')

    def open_pylingual(self):
        QDesktopServices.openUrl(QUrl('https://pylingual.io/'))
        self.append_log('[+] Opened pylingual.io', 'success')

    def open_extracted_folder(self):
        if self.extracted_path and os.path.exists(self.extracted_path):
            if QDesktopServices.openUrl(QUrl.fromLocalFile(self.extracted_path)):
                self.append_log(f'[+] Opened folder: {self.extracted_path}', 'success')
            else:
                self.append_log(f'[!] Could not open: {self.extracted_path}', 'error')
        else:
            self.append_log('[!] No extracted folder available', 'warning')