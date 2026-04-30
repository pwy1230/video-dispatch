# -*- coding: utf-8 -*-
"""
数据库模型模块
使用 SQLite 数据库（适配 PythonAnywhere 免费部署）
"""

import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# 数据库文件路径（基于项目目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(BASE_DIR, 'video_dispatch.db')


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dict_from_row(row):
    """将数据库行转换为字典"""
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(zip([d[0] for d in row.description], row))


def init_db():
    """初始化数据库，创建必要的表"""
    conn = get_db()
    cursor = conn.cursor()
    
    # SQLite 建表语句
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'uploader', 'employee')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            cloudinary_public_id TEXT,
            cloudinary_url TEXT,
            file_size INTEGER DEFAULT 0,
            uploader_id INTEGER NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_assigned BOOLEAN DEFAULT 0,
            FOREIGN KEY (uploader_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS download_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            user_id INTEGER,
            client_identifier TEXT NOT NULL,
            device_info TEXT,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos(id)
        )
    ''')
    
    # 检查是否需要迁移旧表
    cursor.execute("PRAGMA table_info(download_records)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'client_identifier' not in columns:
        cursor.execute('ALTER TABLE download_records ADD COLUMN client_identifier TEXT NOT NULL DEFAULT ""')
        cursor.execute('ALTER TABLE download_records ADD COLUMN device_info TEXT')
    
    # 添加 Cloudinary 相关字段（如果不存在）
    cursor.execute("PRAGMA table_info(videos)")
    video_columns = [col[1] for col in cursor.fetchall()]
    if 'cloudinary_public_id' not in video_columns:
        cursor.execute('ALTER TABLE videos ADD COLUMN cloudinary_public_id TEXT')
        cursor.execute('ALTER TABLE videos ADD COLUMN cloudinary_url TEXT')
    
    # 检查默认管理员是否存在
    cursor.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('admin',))
    if cursor.fetchone()[0] == 0:
        password_hash = generate_password_hash('admin123')
        cursor.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            ('admin', password_hash, 'admin')
        )
        print("✓ 已创建默认管理员账号: admin / admin123")
    
    conn.commit()
    conn.close()
    print("✓ 数据库初始化完成")


def add_user(username, password, role):
    """添加新用户"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return False, "用户名已存在"
        
        password_hash = generate_password_hash(password)
        
        cursor.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            (username, password_hash, role)
        )
        
        conn.commit()
        conn.close()
        return True, f"用户 {username} 创建成功"
    except Exception as e:
        conn.close()
        return False, f"创建用户失败: {str(e)}"


def verify_user(username, password):
    """验证用户登录"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, username, password_hash, role FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(dict_from_row(user)['password_hash'], password):
        return dict_from_row(user)
    return None


def get_user_by_id(user_id):
    """根据ID获取用户信息"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, username, role, created_at FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict_from_row(user) if user else None


def get_all_users():
    """获取所有用户列表"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, username, role, created_at FROM users ORDER BY created_at DESC')
    users = [dict_from_row(row) for row in cursor.fetchall()]
    conn.close()
    return users


def delete_user(user_id):
    """删除用户"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM users WHERE id = ? AND role != ?', (user_id, 'admin'))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def add_video(original_filename, stored_filename, file_size, uploader_id, 
               cloudinary_public_id=None, cloudinary_url=None):
    """添加视频到视频池"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        '''INSERT INTO videos (original_filename, stored_filename, file_size, uploader_id,
           cloudinary_public_id, cloudinary_url) VALUES (?, ?, ?, ?, ?, ?)''',
        (original_filename, stored_filename, file_size, uploader_id,
         cloudinary_public_id, cloudinary_url)
    )
    video_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return video_id


def get_available_videos():
    """获取所有可用的（未被下载的）视频"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT v.id, v.original_filename, v.file_size, v.uploaded_at, 
               v.cloudinary_public_id, v.cloudinary_url,
               u.username as uploader_name
        FROM videos v
        JOIN users u ON v.uploader_id = u.id
        WHERE v.is_assigned = 0
        ORDER BY v.uploaded_at DESC
    ''')
    
    videos = [dict_from_row(row) for row in cursor.fetchall()]
    conn.close()
    return videos


def get_all_videos():
    """获取所有视频（包括已分配的）"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT v.id, v.original_filename, v.file_size, v.uploaded_at, v.is_assigned,
               v.cloudinary_public_id, v.cloudinary_url,
               u.username as uploader_name
        FROM videos v
        JOIN users u ON v.uploader_id = u.id
        ORDER BY v.uploaded_at DESC
    ''')
    
    videos = [dict_from_row(row) for row in cursor.fetchall()]
    conn.close()
    return videos


def get_video_by_id(video_id):
    """根据ID获取视频信息"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM videos WHERE id = ?', (video_id,))
    video = cursor.fetchone()
    conn.close()
    return dict_from_row(video) if video else None


def check_daily_limit(client_identifier):
    """检查同一IP/设备今日是否已达下载上限"""
    conn = get_db()
    cursor = conn.cursor()
    
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = today_start.strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        SELECT COUNT(*) FROM download_records 
        WHERE client_identifier = ? AND downloaded_at >= ?
    ''', (client_identifier, today_str))
    
    count = cursor.fetchone()[0]
    conn.close()
    
    return count >= 1


def assign_random_video(client_identifier, device_info=None, user_id=None):
    """随机分配一个视频给客户端"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 获取一个随机可用视频
    cursor.execute('''
        SELECT id, original_filename, stored_filename, cloudinary_public_id, cloudinary_url
        FROM videos 
        WHERE is_assigned = 0
        ORDER BY RANDOM() 
        LIMIT 1
    ''')
    
    video = cursor.fetchone()
    
    if not video:
        conn.close()
        return None
    
    video = dict_from_row(video)
    
    # 标记视频为已分配
    cursor.execute('UPDATE videos SET is_assigned = 1 WHERE id = ?', (video['id'],))
    
    # 创建下载记录
    cursor.execute(
        'INSERT INTO download_records (video_id, user_id, client_identifier, device_info) VALUES (?, ?, ?, ?)',
        (video['id'], user_id, client_identifier, device_info)
    )
    
    conn.commit()
    conn.close()
    return video


def get_download_records(limit=None, user_id=None, client_identifier=None):
    """获取下载记录"""
    conn = get_db()
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute('''
            SELECT d.id, d.downloaded_at, d.client_identifier, d.device_info,
                   v.original_filename, v.id as video_id, v.cloudinary_url,
                   u.username
            FROM download_records d
            JOIN videos v ON d.video_id = v.id
            LEFT JOIN users u ON d.user_id = u.id
            WHERE d.user_id = ?
            ORDER BY d.downloaded_at DESC
        ''', (user_id,))
    elif client_identifier:
        cursor.execute('''
            SELECT d.id, d.downloaded_at, d.client_identifier, d.device_info,
                   v.original_filename, v.id as video_id, v.cloudinary_url,
                   u.username
            FROM download_records d
            JOIN videos v ON d.video_id = v.id
            LEFT JOIN users u ON d.user_id = u.id
            WHERE d.client_identifier = ?
            ORDER BY d.downloaded_at DESC
        ''', (client_identifier,))
    else:
        sql = '''
            SELECT d.id, d.downloaded_at, d.client_identifier, d.device_info,
                   v.original_filename, v.id as video_id, v.cloudinary_url,
                   u.username
            FROM download_records d
            JOIN videos v ON d.video_id = v.id
            LEFT JOIN users u ON d.user_id = u.id
            ORDER BY d.downloaded_at DESC
        '''
        if limit:
            sql += f' LIMIT {limit}'
        cursor.execute(sql)
    
    records = [dict_from_row(row) for row in cursor.fetchall()]
    conn.close()
    return records


def delete_video(video_id):
    """删除视频"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 只有未分配的视频才能删除
    cursor.execute('DELETE FROM videos WHERE id = ? AND is_assigned = 0', (video_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_stats():
    """获取统计数据"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 视频池数量
    cursor.execute('SELECT COUNT(*) FROM videos WHERE is_assigned = 0')
    available = cursor.fetchone()[0]
    
    # 已分配数量
    cursor.execute('SELECT COUNT(*) FROM videos WHERE is_assigned = 1')
    assigned = cursor.fetchone()[0]
    
    # 用户数量
    cursor.execute('SELECT role, COUNT(*) FROM users GROUP BY role')
    role_counts = {}
    for row in cursor.fetchall():
        role_counts[row[0]] = row[1]
    
    # 下载记录数量
    cursor.execute('SELECT COUNT(*) FROM download_records')
    downloads = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'available_videos': available,
        'assigned_videos': assigned,
        'total_videos': available + assigned,
        'total_users': sum(role_counts.values()),
        'admin_count': role_counts.get('admin', 0),
        'uploader_count': role_counts.get('uploader', 0),
        'employee_count': role_counts.get('employee', 0),
        'total_downloads': downloads
    }


if __name__ == '__main__':
    # 初始化数据库
    init_db()
