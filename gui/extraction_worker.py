import os
import traceback
from PyQt6.QtCore import QThread, pyqtSignal
from core.pyinstaller_extractor import PyInstArchive
from core.nuitka_extractor import find_all_candidates, attempt_at_candidate
from core.paths import get_extraction_dir

class ExtractionWorker(QThread):
    log_message = pyqtSignal(str, str)
    progress_update = pyqtSignal(int, int)
    finished_extraction = pyqtSignal(bool, str)
    file_count_known = pyqtSignal(int)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path

    def run(self):
        try:
            self._run_pyinstaller_then_nuitka()
        except Exception as e:
            self.log_message.emit(f'[!] Fatal error: {str(e)}', 'error')
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    self.log_message.emit(line, 'error')
            self.finished_extraction.emit(False, '')

    def _run_pyinstaller_then_nuitka(self):
        def log_fn(msg):
            self.log_message.emit(str(msg), self._classify(str(msg)))

        arch = PyInstArchive(self.path, log_fn=log_fn)
        if arch.open() and arch.checkFile() and arch.getCArchiveInfo():
            arch.parseTOC()
            self.file_count_known.emit(len(arch.tocList))

            def progress_cb(done, total):
                self.progress_update.emit(done, total)

            arch.extractFiles(progress_cb=progress_cb)
            extracted_dir = arch.extraction_dir
            arch.close()

            self.log_message.emit('=' * 60, 'success')
            self.log_message.emit('[+] PyInstaller extraction completed successfully', 'success')
            self.log_message.emit(f'[+] Extracted to: {extracted_dir}', 'success')
            self.log_message.emit('=' * 60, 'success')
            self.finished_extraction.emit(True, extracted_dir)
            return

        self.log_message.emit('PyInstaller signature not found. Checking for Nuitka...', 'info')
        try:
            candidates = find_all_candidates(self.path)

            if not candidates:
                self.log_message.emit(
                    '[!] No Nuitka signature found either. This file may use a packer '
                    'ExeMiner does not support yet (e.g. cx_Freeze, py2exe).',
                    'warning'
                )
                self.finished_extraction.emit(False, '')
                return

            self.log_message.emit(
                f'[+] Nuitka onefile signature detected ({len(candidates)} candidate offset(s) found)',
                'success'
            )

            extracted_dir = get_extraction_dir('nuitka', self.path)

            with open(self.path, 'rb') as f:
                file_bytes = f.read()

            success_any = False
            for idx, header in candidates:
                ok, cnt, msg = attempt_at_candidate(file_bytes, idx, header, 'PE', extracted_dir)
                self.log_message.emit(
                    f'Trying candidate at offset {idx} header={header} -> {msg}; files_extracted={cnt}',
                    'info'
                )
                if ok:
                    success_any = True
                    break

            if not success_any:
                raise Exception('Nuitka signature found, but extraction failed at every candidate offset')

            self.log_message.emit('=' * 60, 'success')
            self.log_message.emit('[+] Nuitka executable extracted successfully', 'success')
            self.log_message.emit(f'[+] Extracted to: {extracted_dir}', 'success')
            self.log_message.emit('=' * 60, 'success')
            self.finished_extraction.emit(True, extracted_dir)

        except Exception as e:
            self.log_message.emit(f'[!] Nuitka extraction failed: {e}', 'error')
            self.finished_extraction.emit(False, '')

    @staticmethod
    def _classify(msg):
        lowered = msg.lower()
        if msg.startswith('[+]') or 'success' in lowered:
            return 'success'
        if msg.startswith('[!]') and 'error' in lowered:
            return 'error'
        if msg.startswith('[!]'):
            return 'warning'
        return 'info'