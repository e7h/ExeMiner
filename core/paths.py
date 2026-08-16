"""
    extracted/
      pyinstaller/name
      nuitka/name
"""

import os
import sys


def get_app_base_dir():

    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    main_module = sys.modules.get('__main__')
    if main_module is not None and hasattr(main_module, '__file__'):
        return os.path.dirname(os.path.abspath(main_module.__file__))
    return os.getcwd()

def get_extraction_dir(tool, source_path):
    name = os.path.splitext(os.path.basename(source_path))[0]
    target = os.path.join(get_app_base_dir(), 'extracted', tool, name)
    os.makedirs(target, exist_ok=True)
    return target