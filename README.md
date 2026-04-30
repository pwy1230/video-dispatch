# 视频派发网站

一个帮助企业简化视频分发流程的轻量级 Web 应用，支持免费云端部署。

## 功能特性

- 🎬 **视频池管理**：外包团队上传视频到共享视频池
- 🎲 **随机派发**：员工随机获取视频，下载后自动从池子移除
- 👥 **角色权限**：管理员、外包、员工三种角色
- 📊 **记录追踪**：完整记录谁、什么时候、下载了什么视频
- ☁️ **云端存储**：支持 Cloudinary 免费云存储（25GB）
- 📱 **移动端友好**：响应式设计，手机电脑都能用

---

## 免费云端部署方案

本项目支持两种免费部署方案：

| 方案 | 托管平台 | 数据库 | 视频存储 | CPU 限制 |
|------|----------|--------|----------|----------|
| **方案 A** | PythonAnywhere | SQLite（本地） | Cloudinary | 每天100秒 |
| **方案 B** | Render.com | PostgreSQL（云端） | Cloudinary | 每月750小时 |

> 💡 **推荐**：PythonAnywhere 方案更简单，数据库无需额外配置；Render 方案更强大，适合更大流量。

---

## 方案 A：PythonAnywhere 部署（推荐新手）

PythonAnywhere 免费版每天有 100 秒 CPU 时间，使用 SQLite 数据库，视频存储在 Cloudinary。

### 准备工作

你需要准备以下账号：

| 服务 | 用途 | 费用 |
|------|------|------|
| [GitHub](https://github.com) | 代码托管 | 免费 |
| [PythonAnywhere](https://www.pythonanywhere.com) | 网站托管 | 免费 |
| [Cloudinary](https://cloudinary.com) | 视频存储（25GB） | 免费 |

---

### 第一步：上传代码到 GitHub

#### 1.1 创建 GitHub 账号
访问 [github.com](https://github.com)，点击 "Sign up" 注册账号（如果有则跳过）。

#### 1.2 创建新仓库
1. 登录后，点击右上角 **"+"** → **"New repository"**
2. 填写仓库信息：
   - **Repository name**: `video-dispatch`
   - **Description**: `视频派发网站`
   - **Visibility**: Public（公开）
3. 点击 **"Create repository"**

#### 1.3 上传项目代码
在新创建的仓库页面：
1. 点击 **"uploading an existing file"**
2. 把 `视频派发网站` 文件夹里的所有文件拖进去
3. 点击 **"Commit changes"**

> ⚠️ **重要**：请确保以下文件都上传了：
> - `app.py`
> - `models.py`
> - `wsgi.py`
> - `requirements.txt`
> - `.env.example`
> - `setup.sh`
> - `README.md`
> - `templates/` 文件夹
> - `static/` 文件夹

---

### 第二步：注册 Cloudinary（视频存储）

#### 2.1 注册账号
1. 访问 [cloudinary.com/users/register/free](https://cloudinary.com/users/register/free)
2. 填写邮箱、密码、姓名
3. 选择 "Create free account"

#### 2.2 获取 API 密钥
1. 登录后，进入 **Dashboard（仪表盘）**
2. 找到 **"Account Details"** 部分
3. 复制以下信息备用：
   - **Cloud Name**: 如 `abc123xyz`
   - **API Key**: 如 `123456789012345`
   - **API Secret**: 如 `xxxxxxxxxxxxxxxxxxxxx`

---

### 第三步：部署到 PythonAnywhere

#### 3.1 注册 PythonAnywhere
1. 访问 [pythonanywhere.com](https://www.pythonanywhere.com)
2. 点击 **"Pricing"** 标签
3. 选择 **"Hacker (free)"** 免费计划
4. 注册账号（用邮箱验证）

#### 3.2 打开 Bash 控制台
1. 登录后，点击顶部 **"Dashboard"**
2. 在 **"Start a recent console"** 下点击 **"New console"** → **"bash"**

#### 3.3 克隆代码
在 Bash 控制台中运行：

```bash
cd ~ && mkdir -p mysite && cd mysite
git clone https://github.com/pwy1230/video-dispatch.git .
```

#### 3.4 运行一键部署脚本

```bash
bash setup.sh
```

脚本会提示你输入：
- **Cloudinary Cloud Name**: 你的 Cloud Name
- **Cloudinary API Key**: 你的 API Key
- **Cloudinary API Secret**: 你的 API Secret

#### 3.5 配置 Web 应用

1. 返回 PythonAnywhere Dashboard
2. 点击顶部 **"Web"** 标签
3. 点击 **"Add a new web app"**
4. 选择 **"Manual configuration"**
5. 选择 **"Python 3.11"**
6. 点击 **"Next"**

#### 3.6 配置 WSGI 文件

1. 在 Web 页面找到 **"WSGI configuration file"**，点击链接
2. **删除所有内容**，替换为：

```python
import os
import sys

project_home = os.path.expanduser('~/mysite')
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.chdir(project_home)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_home, '.env'))

from app import app as application
```

3. 点击 **Save** 保存

#### 3.7 配置静态文件

在 Web 页面找到 **"Static files"** 部分，点击 **"Enter URL"** 添加：

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/你的用户名/mysite/static` |

#### 3.8 设置虚拟环境

在 Web 页面找到 **"Virtualenv"** 部分：
1. 点击 **"Enter the path to a virtualenv"**
2. 输入：`/home/你的用户名/mysite/venv`

#### 3.9 重启应用

1. 点击页面顶部的绿色 **"Reload your_username.pythonanywhere.com"** 按钮
2. 等待几秒钟

---

### 第四步：验证部署

### 4.1 打开网站
在浏览器访问：`https://你的用户名.pythonanywhere.com`

### 4.2 测试功能
1. 首页应该能看到员工下载页面
2. 点击登录，输入默认账号：
   - **用户名**: `admin`
   - **密码**: `admin123`
3. 登录后进入管理后台，可以：
   - 添加外包账号
   - 上传视频
   - 查看下载记录

> ⚠️ **重要**：首次使用后请立即修改管理员密码！

---

### 常见问题

#### Q: 网站打开提示 500 错误？
1. 点击 Web 页面顶部的 **"View your logs"**
2. 查看 error log 找出问题
3. 常见问题：
   - `.env` 文件未创建 → 重新运行 `bash setup.sh`
   - 环境变量未加载 → 检查 WSGI 文件是否正确

#### Q: 视频上传失败？
1. 检查 Cloudinary 环境变量是否配置正确
2. 在 Bash 中运行：`cat .env` 查看配置
3. Cloudinary 免费版单个文件最大 100MB

#### Q: 免费版有什么限制？
- **PythonAnywhere**：每天 100 秒 CPU 时间（下载视频不占CPU，因为直接重定向到 Cloudinary）
- **Cloudinary**：每月 25GB 带宽和存储
- **SQLite**：数据库在本地，文件不超过 100MB

#### Q: CPU 时间不够用？
- 视频下载直接重定向到 Cloudinary，**不消耗服务器 CPU**
- 只有上传视频、访问管理页面等操作会消耗 CPU
- 免费版每天 100 秒对于小团队绰绰有余

---

## 方案 B：Render.com 部署（适合大流量）

> 如果 PythonAnywhere 的 CPU 限制不够用，可以使用 Render 方案。

### 准备工作

| 服务 | 用途 | 费用 |
|------|------|------|
| [GitHub](https://github.com) | 代码托管 | 免费 |
| [Render](https://render.com) | 网站托管 + 数据库 | 免费 |
| [Cloudinary](https://cloudinary.com) | 视频存储（25GB） | 免费 |

---

### 第一步：上传代码到 GitHub
（同方案 A）

### 第二步：注册 Cloudinary
（同方案 A）

### 第三步：注册 Render

#### 3.1 创建 PostgreSQL 数据库

1. 登录 [render.com](https://render.com)
2. 点击 **"New +"** → **"PostgreSQL"**
3. 配置数据库：
   - **Name**: `video-dispatch-db`
   - **Database**: `video_dispatch`
4. 点击 **"Create Database"**
5. 创建完成后，复制 **"Internal Database URL"**

#### 3.2 创建 Web 服务

1. 点击 **"New +"** → **"Web Service"**
2. 连接你的 GitHub 仓库
3. 配置服务：
   - **Name**: `video-dispatch`
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Plan**: `Free`

#### 3.3 配置环境变量

| 变量名 | 值 |
|--------|-----|
| `DATABASE_URL` | PostgreSQL 的 Internal Database URL |
| `SECRET_KEY` | 随机字符串 |
| `CLOUDINARY_CLOUD_NAME` | 你的 Cloud Name |
| `CLOUDINARY_API_KEY` | 你的 API Key |
| `CLOUDINARY_API_SECRET` | 你的 API Secret |

---

### 第四步：验证部署
（同方案 A）

---

## 本地开发

如果你想在本地运行项目：

### 1. 克隆项目
```bash
git clone https://github.com/pwy1230/video-dispatch.git
cd video-dispatch
```

### 2. 创建虚拟环境
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 创建 .env 文件
复制 `.env.example` 为 `.env`，填入你的 Cloudinary 配置：
```bash
cp .env.example .env
```

### 5. 运行
```bash
python app.py
```

打开浏览器访问：**http://127.0.0.1:5000**

---

## 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |

---

## 角色说明

### 管理员
- 查看所有下载记录
- 查看视频池状态
- 管理用户（添加/删除外包和员工账号）
- 删除视频

### 外包
- 上传视频到视频池
- 查看已上传视频列表

### 员工
- 从视频池随机下载一个视频（每天1次）
- 查看自己的下载记录

---

## 目录结构

```
视频派发网站/
├── app.py              # Flask 主程序
├── models.py           # 数据库模型
├── wsgi.py             # PythonAnywhere WSGI 入口
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量模板
├── setup.sh            # 一键部署脚本
├── runtime.txt         # Python 版本
├── README.md           # 项目说明
├── templates/          # HTML 模板
│   ├── login.html
│   ├── admin_dashboard.html
│   ├── upload.html
│   ├── download.html
│   └── download_success.html
└── static/
    └── css/style.css   # 样式文件
```

---

## 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| 后端 | Flask | Web 框架 |
| 数据库 | SQLite（本地）/ PostgreSQL（云端） | 数据存储 |
| 文件存储 | Cloudinary | 视频云存储 |
| 部署 | PythonAnywhere / Render | 云端托管 |

---

## License

MIT License
