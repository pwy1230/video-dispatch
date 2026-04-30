# 视频派发网站

一个帮助企业简化视频分发流程的轻量级 Web 应用，支持免费云端部署。

## 功能特性

- 🎬 **视频池管理**：外包团队上传视频到共享视频池
- 🎲 **随机派发**：员工随机获取视频，下载后自动从池子移除
- 👥 **角色权限**：管理员、外包、员工三种角色
- 📊 **记录追踪**：完整记录谁、什么时候、下载了什么视频
- ☁️ **云端存储**：支持 Cloudinary 免费云存储（25GB）
- 📱 **移动端友好**：响应式设计，手机电脑都能用

## 免费云端部署（新手教程）

本项目可以**完全免费**部署到 Render.com，使用 PostgreSQL 数据库和 Cloudinary 视频存储。

### 准备工作

你需要准备以下免费账号：

| 服务 | 用途 | 费用 |
|------|------|------|
| [GitHub](https://github.com) | 代码托管 | 免费 |
| [Render](https://render.com) | 网站托管 + 数据库 | 免费 |
| [Cloudinary](https://cloudinary.com) | 视频存储（25GB） | 免费 |

---

## 第一步：上传代码到 GitHub

### 1.1 创建 GitHub 账号
访问 [github.com](https://github.com)，点击 "Sign up" 注册账号（如果有则跳过）。

### 1.2 创建新仓库
1. 登录后，点击右上角 **"+"** → **"New repository"**
2. 填写仓库信息：
   - **Repository name**: `video-dispatch`（或其他你喜欢的名字）
   - **Description**: `视频派发网站`
   - **Visibility**: Public（公开）
3. 点击 **"Create repository"**

### 1.3 上传项目代码
在新创建的仓库页面：
1. 点击 **"uploading an existing file"**
2. 把 `视频派发网站` 文件夹里的所有文件拖进去
3. 点击 **"Commit changes"**

> ⚠️ **重要**：请确保以下文件都上传了：
> - `app.py`
> - `models.py`
> - `requirements.txt`
> - `render.yaml`
> - `runtime.txt`
> - `README.md`
> - `templates/` 文件夹（整个文件夹）

---

## 第二步：注册 Cloudinary（免费视频存储）

### 2.1 注册账号
1. 访问 [cloudinary.com/users/register/free](https://cloudinary.com/users/register/free)
2. 填写邮箱、密码、姓名
3. 选择 "Create free account"

### 2.2 获取 API 密钥
1. 登录后，进入 **Dashboard（仪表盘）**
2. 找到 **"Account Details"** 部分
3. 复制以下信息备用：
   - **Cloud Name**: 如 `abc123xyz`
   - **API Key**: 如 `123456789012345`
   - **API Secret**: 如 `xxxxxxxxxxxxxxxxxxxxx`

> 📝 记下这三个值，后面配置 Render 时会用到。

---

## 第三步：注册 Render（网站托管 + 数据库）

### 3.1 注册账号
1. 访问 [render.com](https://render.com)
2. 点击 **"Get started for free"**
3. 使用 GitHub 账号登录（推荐）

### 3.2 创建 PostgreSQL 数据库（免费）

1. 在 Render Dashboard 点击 **"New +"** → **"PostgreSQL"**
2. 配置数据库：
   - **Name**: `video-dispatch-db`（随便起）
   - **Database**: `video_dispatch`
   - **User**: `video_dispatch_user`
3. 点击 **"Create Database"**
4. 等待创建完成（约1分钟）
5. 创建完成后，在详情页复制 **"Internal Database URL"**

> ⚠️ 格式类似：`postgres://xxx:xxx@xxx.cloud.postgres.database.azure.com:5432/video_dispatch`

### 3.3 创建 Web 服务

1. 点击 **"New +"** → **"Web Service"**
2. 选择 **"Configure account"** 连接你的 GitHub 账号
3. 选择你刚才创建的 GitHub 仓库
4. 配置服务：
   - **Name**: `video-dispatch`（你的网站名字）
   - **Region**: 选择离你最近的（如 Singapore）
   - **Branch**: `main`
   - **Root Directory**: （留空）
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Plan**: `Free`

5. 点击 **"Create Web Service"**

### 3.4 配置环境变量

在服务创建页面的 **"Environment"** 标签下，点击 **"Add Environment Variable"**，添加以下变量：

| 变量名 | 值 |
|--------|-----|
| `DATABASE_URL` | 粘贴第二步复制的 PostgreSQL URL |
| `SECRET_KEY` | 输入一串随机字符（如 `my-secret-key-123456`） |
| `CLOUDINARY_CLOUD_NAME` | 你的 Cloudinary Cloud Name |
| `CLOUDINARY_API_KEY` | 你的 Cloudinary API Key |
| `CLOUDINARY_API_SECRET` | 你的 Cloudinary API Secret |

添加完成后，点击 **"Save Changes"**。

Render 会自动重新部署。

---

## 第四步：验证部署

### 4.1 检查部署状态
1. 在 Render 的 Web Service 页面查看 **"Deployments"**
2. 如果显示 ✅ 绿色，说明部署成功
3. 点击服务名称旁边的 URL（如 `https://video-dispatch.onrender.com`）

### 4.2 测试网站
1. 打开网站，应该能看到员工下载页面
2. 点击登录，输入默认账号：
   - **用户名**: `admin`
   - **密码**: `admin123`
3. 登录后进入管理后台，可以：
   - 添加外包账号
   - 上传视频
   - 查看下载记录

> ⚠️ **重要**：首次使用后请立即修改管理员密码！

---

## 常见问题

### Q: 部署失败怎么办？
1. 查看 Render 的 **"Logs"** 标签页
2. 常见错误：
   - **依赖安装失败**：检查 requirements.txt 格式
   - **环境变量缺失**：确保所有变量都已添加
   - **数据库连接失败**：检查 DATABASE_URL 是否正确

### Q: 视频上传失败？
1. 检查 Cloudinary 环境变量是否配置正确
2. Cloudinary 免费版单个文件最大 100MB
3. 查看 Render 日志中的具体错误信息

### Q: 免费版有什么限制？
- **Render**: 每月 750 小时（15分钟 × 30天），闲置 15 分钟自动休眠
- **Cloudinary**: 每月 25GB 带宽和存储
- **PostgreSQL**: 1GB 存储空间

### Q: 如何让网站不休眠？
由于 Render 免费版的限制，网站闲置 15 分钟后会自动休眠，下次访问时会冷启动（约 30 秒）。这是正常的。

如果需要保持在线，可以：
1. 升级到 Render Paid Plan（约 $7/月）
2. 使用 Uptime Robot 等免费监控服务定时 ping 你的网站

---

## 本地开发

如果你想在本地运行项目：

### 1. 克隆项目
```bash
git clone https://github.com/你的用户名/video-dispatch.git
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

### 4. 运行
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
├── requirements.txt    # Python 依赖
├── render.yaml         # Render 部署配置
├── runtime.txt         # Python 版本
├── README.md           # 项目说明
├── templates/          # HTML 模板
│   ├── login.html
│   ├── admin_dashboard.html
│   ├── upload.html
│   ├── download.html
│   └── download_success.html
└── static/
    └── videos/         # 本地视频存储（仅开发用）
```

---

## 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| 后端 | Flask | Web 框架 |
| 数据库 | PostgreSQL | 数据存储 |
| 文件存储 | Cloudinary | 视频云存储 |
| 部署 | Render | 云端托管 |

---

## 视频存储说明

- **云端部署**：视频存储在 Cloudinary（推荐），数据库只存储 URL
- **本地开发**：视频存储在 `static/videos` 目录

---

## License

MIT License
