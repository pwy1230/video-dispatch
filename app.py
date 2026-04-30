# -*- coding: utf-8 -*-
"""
视频派发网站 - Flask 主程序
适配 PythonAnywhere 免费部署（SQLite + Cloudinary）
"""

import os
import uuid
import tempfile
import shutil
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

# 加载 .env 环境变量
from dotenv import load_dotenv
load_dotenv()

from werkzeug.utils import secure_filename

from models import (
    init_db, add_user, verify_user, get_user_by_id,
    get_all_users, delete_user, get_stats,
    add_video, get_available_videos, get_all_videos, 
    get_video_by_id, assign_random_video, delete_video,
    get_download_records, check_daily_limit,
    add_image_group, get_image_group_items, delete_image_group,
    add_screenshot, get_screenshots_by_video, get_all_screenshots, 
    get_screenshots_by_device, get_screenshot_stats,
    create_announcement, get_active_announcements, get_all_announcements,
    get_announcement_by_id, update_announcement, delete_announcement,
    toggle_announcement, get_announcement_stats
)

# ============== Flask 应用配置 ==============
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', 'wmv'}
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB

app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 本地存储路径（仅本地开发使用）
UPLOAD_FOLDER = 'static/videos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============== Cloudinary 配置 ==============
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Cloudinary 配置
cloudinary_config = {
    'cloud_name': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'api_key': os.environ.get('CLOUDINARY_API_KEY'),
    'api_secret': os.environ.get('CLOUDINARY_API_SECRET')
}

# 判断是否使用 Cloudinary
USE_CLOUDINARY = all(cloudinary_config.values())

if USE_CLOUDINARY:
    cloudinary.config(
        cloud_name=cloudinary_config['cloud_name'],
        api_key=cloudinary_config['api_key'],
        api_secret=cloudinary_config['api_secret']
    )
    print("✓ Cloudinary 已配置，视频将存储到云端")
else:
    print("⚠ Cloudinary 未配置，视频将存储到本地（仅适合本地开发）")


# ============== 辅助函数 ==============

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_logged_in():
    """检查用户是否已登录"""
    return 'user_id' in session


def get_current_user():
    """获取当前登录用户信息"""
    if is_logged_in():
        return get_user_by_id(session['user_id'])
    return None


def login_required(role=None):
    """登录验证装饰器"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            if not is_logged_in():
                return redirect(url_for('login'))
            if role and get_current_user()['role'] != role and get_current_user()['role'] != 'admin':
                flash('您没有权限访问此页面', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator


def get_client_identifier():
    """获取客户端标识 - 优先使用设备ID，其次IP"""
    device_id = request.args.get('device_id') or request.headers.get('X-Device-ID') or request.headers.get('X-Client-ID') or request.form.get('device_id')
    if device_id:
        return f"device_{device_id}"
    
    ip = request.headers.get('X-Forwarded-For', request.headers.get('X-Real-IP', request.remote_addr))
    if ip:
        if ',' in ip:
            ip = ip.split(',')[0].strip()
        return f"ip_{ip}"
    
    return f"anon_{uuid.uuid4().hex[:16]}"


def get_device_info():
    """获取设备信息"""
    user_agent = request.headers.get('User-Agent', '')
    if 'Mobile' in user_agent or 'Android' in user_agent or 'iPhone' in user_agent:
        return 'mobile'
    elif 'iPad' in user_agent:
        return 'tablet'
    return 'desktop'


def format_file_size(size_bytes):
    """格式化文件大小显示"""
    if not size_bytes:
        return '0 B'
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_datetime(dt_str):
    """格式化日期时间显示"""
    if dt_str:
        try:
            if isinstance(dt_str, str):
                dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            else:
                dt = dt_str
            return dt.strftime('%Y-%m-%d %H:%M')
        except:
            return str(dt_str)
    return ''


def get_cloudinary_download_url(cloudinary_url, original_filename):
    """
    获取 Cloudinary 直接下载链接
    避免服务器中转，节省 CPU 秒数
    """
    if not cloudinary_url:
        return None
    
    # Cloudinary 的直接下载链接格式：在 URL 后面加上 ?fl_attachment
    # 或者使用 /fl_attachment/ 路径
    base_url = cloudinary_url.split('/upload/')[0] + '/upload/'
    path_part = cloudinary_url.split('/upload/')[1] if '/upload/' in cloudinary_url else cloudinary_url
    
    # 构建下载 URL，使用 fl_attachment 强制下载
    download_url = base_url + 'fl_attachment/' + path_part
    
    return download_url


# ============== Cloudinary 签名直传 API ==============

@app.route('/api/upload-signature')
@login_required(role='uploader')
def api_upload_signature():
    """
    API: 获取 Cloudinary 上传签名
    前端直传到 Cloudinary 时需要此签名进行身份验证
    支持 type=video 或 type=image
    """
    if not USE_CLOUDINARY:
        return jsonify({'success': False, 'message': 'Cloudinary 未配置'}), 400
    
    upload_type = request.args.get('type', 'video')
    
    import hashlib
    import time
    
    timestamp = str(int(time.time()))
    
    # 根据类型设置不同的 folder 和 resource_type
    if upload_type == 'image':
        folder = 'image_dispatch'
        resource_type = 'image'
        signature_string = f'folder={folder}&timestamp={timestamp}{cloudinary_config["api_secret"]}'
    else:
        folder = 'video_dispatch'
        resource_type = 'video'
        signature_string = f'folder={folder}&timestamp={timestamp}{cloudinary_config["api_secret"]}'
    
    signature = hashlib.sha1(signature_string.encode()).hexdigest()
    
    return jsonify({
        'success': True,
        'cloud_name': cloudinary_config['cloud_name'],
        'api_key': cloudinary_config['api_key'],
        'timestamp': timestamp,
        'signature': signature,
        'folder': folder,
        'resource_type': resource_type
    })


@app.route('/api/save-upload', methods=['POST'])
@login_required(role='uploader')
def api_save_upload():
    """
    API: 保存前端直传成功后的视频记录
    前端直传到 Cloudinary 成功后调用此接口，将视频信息存入数据库
    支持普通视频上传和图片组上传
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '缺少参数'}), 400
    
    upload_type = data.get('type', 'video')
    publish_requirements = data.get('publish_requirements', '').strip() or None
    
    if upload_type == 'image_group':
        # 图片组上传
        images = data.get('images', [])
        group_name = data.get('group_name', f'图片组_{datetime.now().strftime("%Y%m%d%H%M%S")}')
        
        if not images or len(images) < 1:
            return jsonify({'success': False, 'message': '图片组至少需要1张图片'}), 400
        
        try:
            user = get_current_user()
            video_id = add_image_group(group_name, user['id'], images, publish_requirements=publish_requirements)
            print(f"✓ 图片组记录已保存: {group_name} ({len(images)}张图片)")
            
            return jsonify({
                'success': True,
                'message': f'图片组已保存 ({len(images)}张图片)',
                'video_id': video_id
            })
        except Exception as e:
            return jsonify({'success': False, 'message': f'保存失败: {str(e)}'}), 500
    else:
        # 普通视频上传
        cloudinary_url = data.get('cloudinary_url')
        cloudinary_public_id = data.get('cloudinary_public_id')
        original_filename = data.get('original_filename')
        file_size = data.get('file_size', 0)
        
        if not cloudinary_url or not original_filename:
            return jsonify({'success': False, 'message': '缺少必要参数'}), 400
        
        # 生成存储文件名
        import uuid as uuid_module
        ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'mp4'
        stored_filename = f"{uuid_module.uuid4().hex}.{ext}"
        
        # 保存到数据库
        user = get_current_user()
        add_video(
            original_filename, stored_filename, file_size, user['id'],
            cloudinary_public_id=cloudinary_public_id,
            cloudinary_url=cloudinary_url,
            video_type='video',
            publish_requirements=publish_requirements
        )
        
        print(f"✓ 视频记录已保存: {original_filename}")
        
        return jsonify({
            'success': True,
            'message': '视频记录已保存'
        })


# ============== 截图上传 API ==============

@app.route('/api/screenshot-signature')
def api_screenshot_signature():
    """
    API: 获取截图上传的 Cloudinary 签名
    前端直传到 Cloudinary 时需要此签名进行身份验证
    """
    if not USE_CLOUDINARY:
        return jsonify({'success': False, 'message': 'Cloudinary 未配置'}), 400
    
    import hashlib
    import time
    
    timestamp = str(int(time.time()))
    folder = 'screenshot_dispatch'
    resource_type = 'image'
    signature_string = f'folder={folder}&timestamp={timestamp}{cloudinary_config["api_secret"]}'
    
    signature = hashlib.sha1(signature_string.encode()).hexdigest()
    
    return jsonify({
        'success': True,
        'cloud_name': cloudinary_config['cloud_name'],
        'api_key': cloudinary_config['api_key'],
        'timestamp': timestamp,
        'signature': signature,
        'folder': folder,
        'resource_type': resource_type
    })


@app.route('/api/save-screenshot', methods=['POST'])
def api_save_screenshot():
    """
    API: 保存截图记录
    截图直传 Cloudinary 成功后调用此接口，将截图信息存入数据库
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '缺少参数'}), 400
    
    device_id = data.get('device_id')
    video_id = data.get('video_id')
    cloudinary_url = data.get('cloudinary_url')
    cloudinary_public_id = data.get('cloudinary_public_id', '')
    original_filename = data.get('original_filename', 'screenshot.png')
    video_url = data.get('video_url', '').strip()
    note = data.get('note', '')
    
    if not device_id:
        return jsonify({'success': False, 'message': '缺少设备标识'}), 400
    
    if not video_id:
        return jsonify({'success': False, 'message': '缺少视频ID'}), 400
    
    if not cloudinary_url:
        return jsonify({'success': False, 'message': '缺少截图URL'}), 400
    
    if not video_url:
        return jsonify({'success': False, 'message': '视频链接不能为空'}), 400
    
    try:
        add_screenshot(
            device_id, int(video_id), cloudinary_url, cloudinary_public_id,
            original_filename, video_url, note if note else None
        )
        print(f"✓ 截图记录已保存: device={device_id}, video={video_id}")
        
        return jsonify({
            'success': True,
            'message': '截图记录已保存'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'}), 500


@app.route('/api/screenshots/<int:video_id>')
def api_get_screenshots(video_id):
    """API: 获取某个视频的所有截图"""
    screenshots = get_screenshots_by_video(video_id)
    
    for s in screenshots:
        s['uploaded_fmt'] = format_datetime(s.get('uploaded_at'))
    
    return jsonify({
        'success': True,
        'screenshots': screenshots
    })


@app.route('/api/device-screenshots')
def api_get_device_screenshots():
    """API: 获取当前设备的所有截图"""
    device_id = request.args.get('device_id')
    
    if not device_id:
        return jsonify({'success': False, 'message': '缺少设备标识'}), 400
    
    screenshots = get_screenshots_by_device(device_id)
    
    for s in screenshots:
        s['uploaded_fmt'] = format_datetime(s.get('uploaded_at'))
    
    return jsonify({
        'success': True,
        'screenshots': screenshots
    })


@app.route('/admin/screenshots')
@login_required(role='admin')
def admin_screenshots():
    """管理员查看所有截图页面"""
    screenshots = get_all_screenshots()
    screenshot_stats = get_screenshot_stats()
    
    for s in screenshots:
        s['uploaded_fmt'] = format_datetime(s.get('uploaded_at'))
    
    return render_template('admin_screenshots.html',
                           screenshots=screenshots,
                           stats=screenshot_stats)


@app.route('/admin/video-pool')
@login_required(role='admin')
def admin_video_pool():
    """视频池管理页面（独立页面）"""
    stats = get_stats()
    videos = get_all_videos()
    
    for v in videos:
        v['file_size_fmt'] = format_file_size(v.get('file_size'))
        v['uploaded_fmt'] = format_datetime(v.get('uploaded_at'))
    
    return render_template('video_pool.html', 
                           stats=stats, 
                           videos=videos)


# ============== 启动时初始化 ==============
with app.app_context():
    init_db()


# ============== 路由定义 ==============

@app.route('/')
def index():
    """首页"""
    if is_logged_in():
        user = get_current_user()
        role = user['role']
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'uploader':
            return redirect(url_for('upload_page'))
        return redirect(url_for('download_page'))
    return redirect(url_for('download_page'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('请输入用户名和密码', 'error')
            return render_template('login.html')
        
        user = verify_user(username, password)
        if user:
            if user['role'] == 'employee':
                flash('员工请直接访问首页下载视频，无需登录', 'info')
                return render_template('login.html')
            
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'欢迎回来，{user["username"]}！', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """用户登出"""
    session.clear()
    flash('已安全退出登录', 'info')
    return redirect(url_for('download_page'))


# ============== 员工下载端（匿名） ==============

@app.route('/download')
def download_page():
    """员工下载页面"""
    client_id = get_client_identifier()
    stats = get_stats()
    records = get_download_records(client_identifier=client_id)
    can_download = not check_daily_limit(client_id)
    announcements = get_active_announcements()
    
    for r in records:
        r['downloaded_fmt'] = format_datetime(r['downloaded_at'])
    
    return render_template('download.html', 
                           client_id=client_id,
                           stats=stats, 
                           records=records,
                           can_download=can_download,
                           announcements=announcements)


@app.route('/download/action')
def download_action():
    """
    执行随机下载
    分配视频后直接重定向到 Cloudinary 下载链接
    如果是图片组则跳转到图片组查看页面
    """
    client_id = get_client_identifier()
    device_info = get_device_info()
    
    if check_daily_limit(client_id):
        flash('今日您已下载过一次视频，请明天再来哦！', 'warning')
        return redirect(url_for('download_page'))
    
    user_id = session.get('user_id') if is_logged_in() else None
    
    video = assign_random_video(client_id, device_info, user_id)
    
    if video:
        # 检查是否是图片组
        if video.get('type') == 'image_group':
            flash(f'恭喜！获得一组图片 "{video["original_filename"]}"', 'success')
            return redirect(url_for('view_image_group', video_id=video['id']))
        
        flash(f'下载成功！视频 "{video["original_filename"]}" 已从池子移除', 'success')
        
        # 直接重定向到 Cloudinary 下载链接，节省 CPU 秒数
        if USE_CLOUDINARY and video.get('cloudinary_url'):
            download_url = get_cloudinary_download_url(
                video['cloudinary_url'], 
                video['original_filename']
            )
            if download_url:
                return redirect(download_url)
        
        # 如果没有 Cloudinary，回退到下载页面
        return redirect(url_for('download_success', video_id=video['id']))
    else:
        flash('暂无可下载的视频，请联系管理员上传新视频', 'warning')
        return redirect(url_for('download_page'))


@app.route('/download/success/<int:video_id>')
def download_success(video_id):
    """下载成功页面（用于本地存储的回退）"""
    video = get_video_by_id(video_id)
    if not video:
        flash('视频不存在', 'error')
        return redirect(url_for('download_page'))
    
    return render_template('download_success.html', video=video)


@app.route('/download/file/<int:video_id>')
def download_file(video_id):
    """
    下载视频文件（本地存储回退）
    Cloudinary 模式下直接重定向，不走此路由
    """
    video = get_video_by_id(video_id)
    if not video:
        flash('视频不存在', 'error')
        return redirect(url_for('download_page'))
    
    original_filename = video['original_filename']
    
    # Cloudinary 模式下不应该走到这里，因为 download_action 已直接重定向
    # 这里作为备用方案：如果有 Cloudinary URL 但还是走到这里，则生成下载链接
    if USE_CLOUDINARY and video.get('cloudinary_url'):
        download_url = get_cloudinary_download_url(
            video['cloudinary_url'], 
            original_filename
        )
        if download_url:
            return redirect(download_url)
    
    # 本地文件下载
    if video.get('stored_filename'):
        from flask import send_from_directory
        file_path = os.path.join(UPLOAD_FOLDER, video['stored_filename'])
        if os.path.exists(file_path):
            return send_from_directory(
                UPLOAD_FOLDER, 
                video['stored_filename'],
                as_attachment=True,
                download_name=original_filename
            )
    
    flash('视频文件不存在', 'error')
    return redirect(url_for('download_page'))


@app.route('/api/download/status')
def api_download_status():
    """API: 检查下载状态"""
    client_id = get_client_identifier()
    can_download = not check_daily_limit(client_id)
    stats = get_stats()
    
    return jsonify({
        'can_download': can_download,
        'available_videos': stats['available_videos'],
        'message': '今日已下载' if not can_download else '可以下载'
    })


# ============== 管理员端 ==============

@app.route('/admin')
@login_required(role='admin')
def admin_dashboard():
    """管理员控制台"""
    stats = get_stats()
    announcement_stats = get_announcement_stats()
    videos = get_all_videos()
    users = get_all_users()
    records = get_download_records(limit=50)
    
    for v in videos:
        v['file_size_fmt'] = format_file_size(v.get('file_size'))
        v['uploaded_fmt'] = format_datetime(v.get('uploaded_at'))
    
    for r in records:
        r['downloaded_fmt'] = format_datetime(r.get('downloaded_at'))
    
    return render_template('admin_dashboard.html', 
                           stats=stats, 
                           announcement_stats=announcement_stats,
                           videos=videos, 
                           users=users,
                           records=records)


@app.route('/admin/add_user', methods=['POST'])
@login_required(role='admin')
def admin_add_user():
    """添加用户"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'employee')
    
    if not username or not password:
        flash('用户名和密码不能为空', 'error')
    else:
        success, msg = add_user(username, password, role)
        flash(msg, 'success' if success else 'error')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete_user/<int:user_id>')
@login_required(role='admin')
def admin_delete_user(user_id):
    """删除用户"""
    user = get_user_by_id(user_id)
    if user and user['role'] == 'admin':
        flash('不能删除管理员账号', 'error')
    elif delete_user(user_id):
        flash('用户已删除', 'success')
    else:
        flash('删除失败', 'error')
    return redirect(url_for('admin_dashboard'))


# ============== 公告管理路由 ==============

@app.route('/admin/announcements')
@login_required(role='admin')
def admin_announcements():
    """公告管理页面"""
    announcements = get_all_announcements()
    announcement_stats = get_announcement_stats()
    
    for a in announcements:
        a['created_fmt'] = format_datetime(a.get('created_at'))
        a['updated_fmt'] = format_datetime(a.get('updated_at'))
    
    return render_template('admin_announcements.html',
                           announcements=announcements,
                           stats=announcement_stats)


@app.route('/api/announcements/<int:announcement_id>')
@login_required(role='admin')
def api_get_announcement(announcement_id):
    """API: 获取单个公告详情"""
    announcement = get_announcement_by_id(announcement_id)
    
    if not announcement:
        return jsonify({'success': False, 'message': '公告不存在'}), 404
    
    return jsonify({
        'success': True,
        'announcement': announcement
    })


@app.route('/api/announcement-signature')
@login_required(role='admin')
def api_announcement_signature():
    """
    API: 获取公告图片上传的 Cloudinary 签名
    """
    if not USE_CLOUDINARY:
        return jsonify({'success': False, 'message': 'Cloudinary 未配置'}), 400
    
    import hashlib
    import time
    
    timestamp = str(int(time.time()))
    folder = 'announcement_dispatch'
    resource_type = 'image'
    signature_string = f'folder={folder}&timestamp={timestamp}{cloudinary_config["api_secret"]}'
    
    signature = hashlib.sha1(signature_string.encode()).hexdigest()
    
    return jsonify({
        'success': True,
        'cloud_name': cloudinary_config['cloud_name'],
        'api_key': cloudinary_config['api_key'],
        'timestamp': timestamp,
        'signature': signature,
        'folder': folder,
        'resource_type': resource_type
    })


@app.route('/api/save-announcement', methods=['POST'])
@login_required(role='admin')
def api_save_announcement():
    """API: 创建公告"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '缺少参数'}), 400
    
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    image_url = data.get('image_url')
    image_cloudinary_id = data.get('image_cloudinary_id')
    
    if not title:
        return jsonify({'success': False, 'message': '公告标题不能为空'}), 400
    
    try:
        announcement_id = create_announcement(
            title=title,
            content=content,
            image_url=image_url,
            image_cloudinary_id=image_cloudinary_id
        )
        print(f"✓ 公告已创建: {title}")
        
        return jsonify({
            'success': True,
            'message': '公告创建成功',
            'announcement_id': announcement_id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'创建失败: {str(e)}'}), 500


@app.route('/api/update-announcement', methods=['POST'])
@login_required(role='admin')
def api_update_announcement():
    """API: 更新公告"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '缺少参数'}), 400
    
    announcement_id = data.get('id')
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    image_url = data.get('image_url')
    image_cloudinary_id = data.get('image_cloudinary_id')
    is_active = data.get('is_active')
    
    if not announcement_id:
        return jsonify({'success': False, 'message': '缺少公告ID'}), 400
    
    if not title:
        return jsonify({'success': False, 'message': '公告标题不能为空'}), 400
    
    try:
        # 处理图片：如果没有传新图片，设置 image_url=None 以保留原图
        if image_url == '':
            image_url = None
            image_cloudinary_id = None
        
        success = update_announcement(
            announcement_id=announcement_id,
            title=title,
            content=content,
            image_url=image_url,
            image_cloudinary_id=image_cloudinary_id,
            is_active=is_active
        )
        
        if success:
            print(f"✓ 公告已更新: {title}")
            return jsonify({
                'success': True,
                'message': '公告更新成功'
            })
        else:
            return jsonify({'success': False, 'message': '公告不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


@app.route('/api/toggle-announcement/<int:announcement_id>', methods=['POST'])
@login_required(role='admin')
def api_toggle_announcement(announcement_id):
    """API: 切换公告启用/停用状态"""
    try:
        success = toggle_announcement(announcement_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '状态切换成功'
            })
        else:
            return jsonify({'success': False, 'message': '公告不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'}), 500


@app.route('/api/delete-announcement/<int:announcement_id>', methods=['POST'])
@login_required(role='admin')
def api_delete_announcement(announcement_id):
    """API: 删除公告"""
    try:
        # 获取公告信息（用于删除 Cloudinary 图片）
        announcement = get_announcement_by_id(announcement_id)
        
        if not announcement:
            return jsonify({'success': False, 'message': '公告不存在'}), 404
        
        # 删除 Cloudinary 上的图片（如果存在）
        if USE_CLOUDINARY and announcement.get('image_cloudinary_id'):
            try:
                cloudinary.uploader.destroy(announcement['image_cloudinary_id'])
                print(f"✓ 已删除 Cloudinary 上的公告图片: {announcement['image_cloudinary_id']}")
            except Exception as e:
                print(f"⚠ 删除 Cloudinary 图片失败: {e}")
        
        success = delete_announcement(announcement_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '公告已删除'
            })
        else:
            return jsonify({'success': False, 'message': '删除失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500


@app.route('/admin/delete_video/<int:video_id>')
@login_required(role='admin')
def admin_delete_video(video_id):
    """删除视频"""
    video = get_video_by_id(video_id)
    if video:
        # 删除 Cloudinary 上的文件（如果使用）
        if USE_CLOUDINARY and video.get('cloudinary_public_id'):
            try:
                cloudinary.uploader.destroy(video['cloudinary_public_id'])
                print(f"✓ 已删除 Cloudinary 上的文件: {video['cloudinary_public_id']}")
            except Exception as e:
                print(f"⚠ 删除 Cloudinary 文件失败: {e}")
        
        # 删除本地文件（如果存在）
        file_path = os.path.join(UPLOAD_FOLDER, video.get('stored_filename', ''))
        if os.path.exists(file_path):
            os.remove(file_path)
        
        if delete_video(video_id):
            flash('视频已删除', 'success')
            return redirect(url_for('admin_dashboard'))
    
    flash('删除失败或视频已被下载', 'error')
    return redirect(url_for('admin_dashboard'))


# ============== 图片组下载页面（员工端） ==============

@app.route('/image-group/<int:video_id>')
def view_image_group(video_id):
    """查看图片组页面"""
    video = get_video_by_id(video_id)
    if not video or video.get('type') != 'image_group':
        flash('图片组不存在', 'error')
        return redirect(url_for('download_page'))
    
    # 如果图片组未被分配（通过链接直接访问），则标记为已分配
    client_id = get_client_identifier()
    device_info = get_device_info()
    user_id = session.get('user_id') if is_logged_in() else None
    
    if not video.get('is_assigned'):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE videos SET is_assigned = 1 WHERE id = ?', (video_id,))
        cursor.execute(
            'INSERT INTO download_records (video_id, user_id, client_identifier, device_info) VALUES (?, ?, ?, ?)',
            (video_id, user_id, client_id, device_info)
        )
        conn.commit()
        conn.close()
    
    images = get_image_group_items(video_id)
    
    return render_template('image_group.html', 
                           video=video, 
                           images=images,
                           can_download=True)


@app.route('/api/image-group/<int:video_id>')
def api_get_image_group(video_id):
    """API: 获取图片组信息"""
    video = get_video_by_id(video_id)
    if not video or video.get('type') != 'image_group':
        return jsonify({'success': False, 'message': '图片组不存在'}), 404
    
    images = get_image_group_items(video_id)
    
    return jsonify({
        'success': True,
        'video': video,
        'images': images
    })


# ============== 图片组管理（管理员端） ==============

@app.route('/admin/delete_image_group/<int:video_id>')
@login_required(role='admin')
def admin_delete_image_group(video_id):
    """删除图片组"""
    video = get_video_by_id(video_id)
    if not video or video.get('type') != 'image_group':
        flash('图片组不存在', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # 删除 Cloudinary 上的图片
    deleted, public_ids = delete_image_group(video_id)
    
    if deleted:
        # 删除 Cloudinary 上的文件
        if USE_CLOUDINARY:
            for public_id in public_ids:
                try:
                    cloudinary.uploader.destroy(public_id, resource_type='image')
                    print(f"✓ 已删除 Cloudinary 上的图片: {public_id}")
                except Exception as e:
                    print(f"⚠ 删除 Cloudinary 图片失败: {e}")
        
        flash('图片组已删除', 'success')
    else:
        flash('删除失败或图片组已被下载', 'error')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/api/batch-delete', methods=['POST'])
@login_required(role='admin')
def api_batch_delete():
    """
    API: 批量删除视频或图片组
    接收JSON格式: {"items": [{"id": 1, "type": "video"}, {"id": 2, "type": "image_group"}]}
    """
    data = request.get_json()
    
    if not data or 'items' not in data:
        return jsonify({'success': False, 'message': '缺少参数'}), 400
    
    items = data.get('items', [])
    if not items:
        return jsonify({'success': False, 'message': '没有要删除的项目'}), 400
    
    deleted_count = 0
    errors = []
    
    for item in items:
        item_id = item.get('id')
        item_type = item.get('type')
        
        if not item_id or not item_type:
            errors.append(f'项目数据不完整: {item}')
            continue
        
        try:
            video = get_video_by_id(item_id)
            
            if not video:
                errors.append(f'项目 #{item_id} 不存在')
                continue
            
            # 检查是否已被分配
            if video.get('is_assigned'):
                errors.append(f'{video["original_filename"]} 已被分配，无法删除')
                continue
            
            if item_type == 'image_group':
                # 删除图片组及其所有图片
                deleted, public_ids = delete_image_group(item_id)
                
                if deleted:
                    # 删除 Cloudinary 上的图片文件
                    if USE_CLOUDINARY:
                        for public_id in public_ids:
                            try:
                                cloudinary.uploader.destroy(public_id, resource_type='image')
                                print(f"✓ [批量] 已删除 Cloudinary 上的图片: {public_id}")
                            except Exception as e:
                                print(f"⚠ [批量] 删除 Cloudinary 图片失败: {e}")
                    
                    deleted_count += 1
                    print(f"✓ [批量] 已删除图片组: {video['original_filename']}")
                else:
                    errors.append(f'删除图片组失败: {video["original_filename"]}')
            
            elif item_type == 'video':
                # 删除单个视频
                # 删除 Cloudinary 上的文件
                if USE_CLOUDINARY and video.get('cloudinary_public_id'):
                    try:
                        cloudinary.uploader.destroy(video['cloudinary_public_id'])
                        print(f"✓ [批量] 已删除 Cloudinary 上的视频: {video['cloudinary_public_id']}")
                    except Exception as e:
                        print(f"⚠ [批量] 删除 Cloudinary 文件失败: {e}")
                
                # 删除本地文件
                file_path = os.path.join(UPLOAD_FOLDER, video.get('stored_filename', ''))
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                if delete_video(item_id):
                    deleted_count += 1
                    print(f"✓ [批量] 已删除视频: {video['original_filename']}")
                else:
                    errors.append(f'删除视频失败: {video["original_filename"]}')
            else:
                errors.append(f'未知类型: {item_type}')
        
        except Exception as e:
            errors.append(f'删除项目 #{item_id} 时出错: {str(e)}')
            print(f"⚠ [批量] 删除失败: {e}")
    
    if deleted_count > 0:
        return jsonify({
            'success': True,
            'message': f'成功删除 {deleted_count} 个项目' + (f'，{len(errors)} 个失败' if errors else ''),
            'deleted_count': deleted_count,
            'errors': errors
        })
    else:
        return jsonify({
            'success': False,
            'message': '删除失败: ' + '; '.join(errors) if errors else '没有删除任何项目',
            'errors': errors
        }), 400


# ============== 外包上传端 ==============

@app.route('/upload')
@login_required(role='uploader')
def upload_page():
    """上传页面"""
    user = get_current_user()
    videos = get_available_videos()
    
    for v in videos:
        v['file_size_fmt'] = format_file_size(v.get('file_size'))
        v['uploaded_fmt'] = format_datetime(v.get('uploaded_at'))
    
    return render_template('upload.html', videos=videos, user=user)


@app.route('/upload', methods=['POST'])
@login_required(role='uploader')
def upload_video():
    """处理视频上传"""
    if 'video' not in request.files:
        flash('没有选择文件', 'error')
        return redirect(url_for('upload_page'))
    
    file = request.files['video']
    
    if file.filename == '':
        flash('请选择一个视频文件', 'error')
        return redirect(url_for('upload_page'))
    
    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        ext = original_filename.rsplit('.', 1)[1].lower()
        stored_filename = f"{uuid.uuid4().hex}.{ext}"
        
        # 获取文件大小
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        cloudinary_public_id = None
        cloudinary_url = None
        
        if USE_CLOUDINARY:
            # 上传到 Cloudinary
            try:
                # 创建临时文件
                with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tmp:
                    shutil.copyfileobj(file, tmp)
                    tmp_path = tmp.name
                
                # 上传到 Cloudinary
                upload_result = cloudinary.uploader.upload_large(
                    tmp_path,
                    resource_type='video',
                    folder='video_dispatch',
                    public_id=stored_filename.rsplit('.', 1)[0],
                    chunk_size=6000000  # 6MB chunks for large files
                )
                
                cloudinary_public_id = upload_result.get('public_id')
                cloudinary_url = upload_result.get('secure_url')
                
                # 删除临时文件
                os.remove(tmp_path)
                
                print(f"✓ 视频已上传到 Cloudinary: {cloudinary_public_id}")
                
            except Exception as e:
                flash(f'云端上传失败: {str(e)}，将使用本地存储', 'warning')
                # 回退到本地存储
                file_path = os.path.join(UPLOAD_FOLDER, stored_filename)
                file.save(file_path)
        else:
            # 本地存储
            file_path = os.path.join(UPLOAD_FOLDER, stored_filename)
            file.save(file_path)
        
        # 保存到数据库
        user = get_current_user()
        add_video(
            original_filename, stored_filename, file_size, user['id'],
            cloudinary_public_id=cloudinary_public_id,
            cloudinary_url=cloudinary_url
        )
        
        flash(f'视频 "{original_filename}" 上传成功！', 'success')
    else:
        flash('不支持的文件格式，请上传 MP4、AVI、MOV、MKV 等格式', 'error')
    
    return redirect(url_for('upload_page'))


@app.route('/upload/batch', methods=['POST'])
@login_required(role='uploader')
def upload_video_batch():
    """
    批量处理视频上传（接收多个文件，逐个处理）
    """
    if 'video' not in request.files:
        return jsonify({'success': False, 'message': '没有选择文件'}), 400
    
    files = request.files.getlist('video')
    
    if not files or len(files) == 0:
        return jsonify({'success': False, 'message': '没有选择文件'}), 400
    
    results = []
    success_count = 0
    error_count = 0
    
    for file in files:
        if file.filename == '':
            error_count += 1
            results.append({
                'filename': '',
                'success': False,
                'message': '文件名为空'
            })
            continue
        
        if file and allowed_file(file.filename):
            try:
                original_filename = secure_filename(file.filename)
                ext = original_filename.rsplit('.', 1)[1].lower()
                stored_filename = f"{uuid.uuid4().hex}.{ext}"
                
                # 获取文件大小
                file.seek(0, 2)
                file_size = file.tell()
                file.seek(0)
                
                cloudinary_public_id = None
                cloudinary_url = None
                
                if USE_CLOUDINARY:
                    # 上传到 Cloudinary
                    try:
                        # 创建临时文件
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tmp:
                            shutil.copyfileobj(file, tmp)
                            tmp_path = tmp.name
                        
                        # 上传到 Cloudinary
                        upload_result = cloudinary.uploader.upload_large(
                            tmp_path,
                            resource_type='video',
                            folder='video_dispatch',
                            public_id=stored_filename.rsplit('.', 1)[0],
                            chunk_size=6000000
                        )
                        
                        cloudinary_public_id = upload_result.get('public_id')
                        cloudinary_url = upload_result.get('secure_url')
                        
                        # 删除临时文件
                        os.remove(tmp_path)
                        
                    except Exception as e:
                        # 回退到本地存储
                        file_path = os.path.join(UPLOAD_FOLDER, stored_filename)
                        file.seek(0)
                        file.save(file_path)
                else:
                    # 本地存储
                    file_path = os.path.join(UPLOAD_FOLDER, stored_filename)
                    file.save(file_path)
                
                # 保存到数据库
                user = get_current_user()
                add_video(
                    original_filename, stored_filename, file_size, user['id'],
                    cloudinary_public_id=cloudinary_public_id,
                    cloudinary_url=cloudinary_url
                )
                
                success_count += 1
                results.append({
                    'filename': original_filename,
                    'success': True,
                    'message': '上传成功'
                })
                
            except Exception as e:
                error_count += 1
                results.append({
                    'filename': file.filename,
                    'success': False,
                    'message': str(e)
                })
        else:
            error_count += 1
            results.append({
                'filename': file.filename,
                'success': False,
                'message': '不支持的文件格式'
            })
    
    return jsonify({
        'success': error_count == 0,
        'success_count': success_count,
        'error_count': error_count,
        'total': len(files),
        'results': results
    })


# ============== 健康检查 ==============

@app.route('/health')
def health_check():
    """健康检查端点"""
    return {'status': 'healthy', 'cloudinary': USE_CLOUDINARY}


# ============== 启动应用 ==============

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
