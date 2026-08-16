from __future__ import print_function
import os
import struct
import marshal
import zlib
from uuid import uuid4 as uniquename
from .paths import get_extraction_dir


class CTOCEntry:

    def __init__(self, position, cmprsdDataSize, uncmprsdDataSize, cmprsFlag, typeCmprsData, name):
        self.position = position
        self.cmprsdDataSize = cmprsdDataSize
        self.uncmprsdDataSize = uncmprsdDataSize
        self.cmprsFlag = cmprsFlag
        self.typeCmprsData = typeCmprsData
        self.name = name


class PyInstArchive:
    MAGIC = b'MEI\014\013\012\013\016'
    PYINST20_COOKIE_SIZE = 24
    PYINST21_COOKIE_SIZE = 24 + 64

    def __init__(self, path, log_fn=None):
        self.filePath = path
        self.pycMagic = b'\0' * 4
        self.barePycList = []
        self.log = log_fn or (lambda *a, **k: None)

    def _log(self, *parts):
        self.log(' '.join(str(p) for p in parts))

    def open(self):
        try:
            self.fPtr = open(self.filePath, 'rb')
            self.fileSize = os.stat(self.filePath).st_size
        except Exception as e:
            self._log('[!] Error: Could not open', self.filePath, '-', e)
            return False
        return True

    def close(self):
        try:
            self.fPtr.close()
        except Exception:
            pass

    def checkFile(self):
        self._log('[+] Processing', self.filePath)
        searchChunkSize = 8192
        endPos = self.fileSize
        self.cookiePos = -1

        if endPos < len(self.MAGIC):
            self._log('[!] Error : File is too short or truncated')
            return False

        while True:
            startPos = endPos - searchChunkSize if endPos >= searchChunkSize else 0
            chunkSize = endPos - startPos

            if chunkSize < len(self.MAGIC):
                break

            self.fPtr.seek(startPos, os.SEEK_SET)
            data = self.fPtr.read(chunkSize)

            offs = data.rfind(self.MAGIC)

            if offs != -1:
                self.cookiePos = startPos + offs
                break

            endPos = startPos + len(self.MAGIC) - 1

            if startPos == 0:
                break

        if self.cookiePos == -1:
            self._log('[!] No PyInstaller cookie found (not a PyInstaller archive)')
            return False

        self.fPtr.seek(self.cookiePos + self.PYINST20_COOKIE_SIZE, os.SEEK_SET)
        tail = self.fPtr.read(64)
        if b'python' in tail.lower():
            self.pyinstVer = 21
            self._log('[+] Pyinstaller version: 2.1+')
        else:
            self.pyinstVer = 20
            self._log('[+] Pyinstaller version: 2.0')
        return True

    def getCArchiveInfo(self):
        try:
            if self.pyinstVer == 20:
                self.fPtr.seek(self.cookiePos, os.SEEK_SET)
                (magic, lengthofPackage, toc, tocLen, pyver) = struct.unpack(
                    '!8siiii', self.fPtr.read(self.PYINST20_COOKIE_SIZE)
                )
            else:
                self.fPtr.seek(self.cookiePos, os.SEEK_SET)
                (magic, lengthofPackage, toc, tocLen, pyver, pylibname) = struct.unpack(
                    '!8sIIii64s', self.fPtr.read(self.PYINST21_COOKIE_SIZE)
                )
        except Exception as e:
            self._log('[!] Error : The file is not a pyinstaller , Nuitka archive (getCArchiveInfo failed) -', e)
            return False

        if pyver >= 100:
            self.pymaj, self.pymin = (pyver // 100, pyver % 100)
        else:
            self.pymaj, self.pymin = (pyver // 10, pyver % 10)

        self._log('[+] Python version:', f'{self.pymaj}.{self.pymin}')

        tailBytes = self.fileSize - self.cookiePos - (
            self.PYINST20_COOKIE_SIZE if self.pyinstVer == 20 else self.PYINST21_COOKIE_SIZE
        )
        self.overlaySize = lengthofPackage + tailBytes
        self.overlayPos = self.fileSize - self.overlaySize
        self.tableOfContentsPos = self.overlayPos + toc
        self.tableOfContentsSize = tocLen
        self._log('[+] Length of package:', lengthofPackage)
        return True

    def parseTOC(self):
        self.fPtr.seek(self.tableOfContentsPos, os.SEEK_SET)
        self.tocList = []
        parsedLen = 0

        while parsedLen < self.tableOfContentsSize:
            (entrySize,) = struct.unpack('!i', self.fPtr.read(4))
            nameLen = struct.calcsize('!iIIIBc')
            raw = self.fPtr.read(entrySize - 4)
            try:
                (entryPos, cmprsdDataSize, uncmprsdDataSize, cmprsFlag, typeCmprsData, name) = struct.unpack(
                    '!IIIBc{0}s'.format(entrySize - nameLen), raw
                )
            except Exception as e:
                self._log('[!] Error parsing TOC entry:', e)
                break

            try:
                name = name.decode('utf-8').rstrip('\0')
            except Exception:
                newName = str(uniquename())
                self._log('[!] Warning: File name contains invalid bytes. Using random name', newName)
                name = newName

            if name.startswith('/'):
                name = name.lstrip('/')

            if len(name) == 0:
                name = str(uniquename())
                self._log('[!] Warning: Found an unnamed file. Using random name', name)

            self.tocList.append(
                CTOCEntry(self.overlayPos + entryPos, cmprsdDataSize, uncmprsdDataSize, cmprsFlag, typeCmprsData, name)
            )
            parsedLen += entrySize

        self._log('[+] Found', len(self.tocList), 'files in CArchive')

    def _writeRawData(self, filepath, data):
        nm = filepath.replace('\\', os.path.sep).replace('/', os.path.sep).replace('..', '__')
        nmDir = os.path.dirname(nm)
        if nmDir != '' and not os.path.exists(nmDir):
            os.makedirs(nmDir, exist_ok=True)
        with open(nm, 'wb') as f:
            f.write(data)

    def extractFiles(self, progress_cb=None):
        self._log('[+] Beginning extraction...')

        original_dir = os.getcwd()

        extractionDir = get_extraction_dir('pyinstaller', self.filePath)
        self._log('[+] Extraction directory: ' + extractionDir)
        os.chdir(extractionDir)

        self.extraction_dir = extractionDir

        try:
            for idx, entry in enumerate(self.tocList, 1):
                try:
                    self.fPtr.seek(entry.position, os.SEEK_SET)
                    data = self.fPtr.read(entry.cmprsdDataSize)

                    if entry.cmprsFlag == 1:
                        try:
                            data = zlib.decompress(data)
                        except zlib.error:
                            self._log('[!] Error : Failed to decompress', entry.name)
                            continue

                    if entry.typeCmprsData in (b'd', b'o'):
                        continue

                    basePath = os.path.dirname(entry.name)
                    if basePath != '' and not os.path.exists(basePath):
                        os.makedirs(basePath, exist_ok=True)

                    if entry.typeCmprsData == b's':
                        self._log('[+] Possible entry point:', entry.name + '.pyc')
                        if self.pycMagic == b'\0' * 4:
                            self.barePycList.append(entry.name + '.pyc')
                        self._writePyc(entry.name + '.pyc', data)

                    elif entry.typeCmprsData in (b'M', b'm'):
                        if len(data) >= 4 and data[2:4] == b'\r\n':
                            if self.pycMagic == b'\0' * 4:
                                self.pycMagic = data[0:4]
                            self._writeRawData(entry.name + '.pyc', data)
                        else:
                            if self.pycMagic == b'\0' * 4:
                                self.barePycList.append(entry.name + '.pyc')
                            self._writePyc(entry.name + '.pyc', data)
                    else:
                        self._writeRawData(entry.name, data)
                        if entry.typeCmprsData in (b'z', b'Z'):
                            self._extractPyz(entry.name)

                    if progress_cb:
                        progress_cb(idx, len(self.tocList))

                except Exception as e:
                    self._log('[!] Exception extracting', entry.name, '-', e)

            self._fixBarePycs()
            self._log('[+] Extraction complete')
        finally:
            os.chdir(original_dir)

    def _fixBarePycs(self):
        for pycFilePath in self.barePycList:
            try:
                with open(pycFilePath, 'r+b') as fh:
                    fh.write(self.pycMagic)
            except Exception as e:
                self._log('[!] Could not fix pyc header for', pycFilePath, '-', e)

    def _writePyc(self, filename, data):
        with open(filename, 'wb') as pycFile:
            pycFile.write(self.pycMagic)
            if self.pymaj >= 3 and self.pymin >= 7:
                pycFile.write(b'\0' * 4)
                pycFile.write(b'\0' * 8)
            else:
                pycFile.write(b'\0' * 4)
                if self.pymaj >= 3 and self.pymin >= 3:
                    pycFile.write(b'\0' * 4)
            pycFile.write(data)

    def _extractPyz(self, name):
        import sys

        dirName = name + '_extracted'
        os.makedirs(dirName, exist_ok=True)
        with open(name, 'rb') as f:
            pyzMagic = f.read(4)
            if pyzMagic != b'PYZ\0':
                self._log('[!] Warning: Not a PYZ archive:', name)
                return
            pyzPycMagic = f.read(4)
            if self.pycMagic == b'\0' * 4:
                self.pycMagic = pyzPycMagic
            elif self.pycMagic != pyzPycMagic:
                self.pycMagic = pyzPycMagic
                self._log('[!] Warning: pyc magic mismatch inside PYZ')

            if self.pymaj != sys.version_info.major or self.pymin != sys.version_info.minor:
                self._log('[!] Warning: Running different Python version than the one used to build executable. Skipping PYZ extraction.')
                return

            (tocPosition,) = struct.unpack('!i', f.read(4))
            f.seek(tocPosition, os.SEEK_SET)
            try:
                toc = marshal.load(f)
            except Exception:
                self._log('[!] Unmarshalling FAILED for PYZ, skipping')
                return

            if isinstance(toc, list):
                toc = dict(toc)

            for key in toc.keys():
                ispkg, pos, length = toc[key]
                f.seek(pos, os.SEEK_SET)
                fileName = key
                try:
                    fileName = fileName.decode('utf-8')
                except Exception:
                    pass
                fileName = fileName.replace('..', '__').replace('.', os.path.sep)
                if ispkg == 1:
                    filePath = os.path.join(dirName, fileName, '__init__.pyc')
                else:
                    filePath = os.path.join(dirName, fileName + '.pyc')
                fileDir = os.path.dirname(filePath)
                os.makedirs(fileDir, exist_ok=True)
                try:
                    data = f.read(length)
                    data = zlib.decompress(data)
                except Exception:
                    self._log('[!] Error decompressing', filePath, '- saved as encrypted')
                    open(filePath + '.encrypted', 'wb').write(data)
                else:
                    self._writePyc(filePath, data)