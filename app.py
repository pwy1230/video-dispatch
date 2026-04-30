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
    get_download_records, check_daily_limit
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
    """
    if not USE_CLOUDINARY:
        return jsonify({'success': False, 'message': 'Cloudinary 未配置'}), 400
    
    import hashlib
    import time
    
    timestamp = str(int(time.time()))
    # 签名必须包含所有上传参数，按字母排序拼接
    signature_string = 'folder=video_dispatch&timestamp=' + timestamp + cloudinary_config['api_secret']
    signature = hashlib.sha1(signature_string.encode()).hexdigest()
    
    return jsonify({
        'success': True,
        'cloud_name': cloudinary_config['cloud_name'],
        'api_key': cloudinary_config['api_key'],
        'timestamp': timestamp,
        'signature': signature
    })


@app.route('/api/save-upload', methods=['POST'])
@login_required(role='uploader')
def api_save_upload():
    """
    API: 保存前端直传成功后的视频记录
    前端直传到 Cloudinary 成功后调用此接口，将视频信息存入数据库
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '缺少参数'}), 400
    
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
        cloudinary_url=cloudinary_url
    )
    
    print(f"✓ 视频记录已保存: {original_filename}")
    
    return jsonify({
        'success': True,
        'message': '视频记录已保存'
    })


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
    
    for r in records:
        r['downloaded_fmt'] = format_datetime(r['downloaded_at'])
    
    return render_template('download.html', 
                           client_id=client_id,
                           stats=stats, 
                           records=records,
                           can_download=can_download)


@app.route('/download/action')
def download_action():
    """
    执行随机下载
    分配视频后直接重定向到 Cloudinary 下载链接
    """
    client_id = get_client_identifier()
    device_info = get_device_info()
    
    if check_daily_limit(client_id):
        flash('今日您已下载过一次视频，请明天再来哦！', 'warning')
        return redirect(url_for('download_page'))
    
    user_id = session.get('user_id') if is_logged_in() else None
    
    video = assign_random_video(client_id, device_info, user_id)
    
    if video:
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
