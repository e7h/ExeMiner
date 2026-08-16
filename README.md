# ExeMiner
ExeMiner — GUI tool to rip apart PyInstaller and Nuitka exe's and grab whatever's packed inside (pyc files, resources, etc). Has an optional Rust module that speeds up scanning big onefile exe's, falls back to pure Python if it's not built. Drag &amp; drop, runs on a separate thread so the UI doesn't freeze.
