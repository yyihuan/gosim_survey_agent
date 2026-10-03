#!/usr/bin/env python3
"""兼容旧构建入口；权威正文由当前Node构建器读取。"""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1]
subprocess.run(['node',str(root/'scripts/build_rules_explorer.mjs')],cwd=root,check=True)
