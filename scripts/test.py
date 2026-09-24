"""本仓库统一验证入口，测试只使用临时文件与本机页面。"""
from pathlib import Path
import os
import subprocess
import sys


if __name__ == "__main__":
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    raise SystemExit(subprocess.call([sys.executable, "-X", "utf8", "-m", "pytest", *sys.argv[1:]],
                                    cwd=Path(__file__).resolve().parents[1], env=env))
