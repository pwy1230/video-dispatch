# -*- coding: utf-8 -*-
"""
PythonAnywhere WSGI 入口文件
用于 PythonAnywhere 免费版部署
"""

import os
import sys

# 添加项目目录到 sys.path
# PythonAnywhere 会把代码放在 /home/用户名/mysite/ 下
project_home = os.path.expanduser('~/mysite')
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 切换到项目目录
os.chdir(project_home)

# 导入 Flask 应用
from app import app as application
