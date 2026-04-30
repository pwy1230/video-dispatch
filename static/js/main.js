/**
 * 视频派发网站 - JavaScript 主文件
 */

// ==================== 工具函数 ====================

/**
 * 显示提示消息
 */
function showToast(message, type = 'info') {
    const container = document.querySelector('.flash-messages') || createToastContainer();
    const toast = document.createElement('div');
    toast.className = `flash flash-${type}`;
    toast.innerHTML = `
        <span class="flash-icon">${getIcon(type)}</span>
        <span class="flash-text">${message}</span>
    `;
    container.appendChild(toast);
    
    // 3秒后自动移除
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/**
 * 创建消息容器
 */
function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'flash-messages';
    document.body.appendChild(container);
    return container;
}

/**
 * 根据类型获取图标
 */
function getIcon(type) {
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };
    return icons[type] || icons.info;
}

// ==================== 上传功能 ====================

/**
 * 初始化上传区域
 */
function initUploadZone() {
    const zone = document.querySelector('.upload-zone');
    const input = document.querySelector('.upload-input');
    const form = document.querySelector('#upload-form');
    
    if (!zone || !input) return;
    
    // 点击区域触发文件选择
    zone.addEventListener('click', () => input.click());
    
    // 文件选择后自动提交
    input.addEventListener('change', () => {
        if (input.files.length > 0) {
            // 显示选中文件名
            const fileName = input.files[0].name;
            zone.querySelector('.upload-zone-text').textContent = `已选择: ${fileName}`;
            zone.querySelector('.upload-zone-text').style.color = 'var(--success)';
            
            // 自动提交
            if (form) {
                showToast('正在上传...', 'info');
                form.submit();
            }
        }
    });
    
    // 拖拽上传
    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });
    
    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });
    
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0 && input) {
            input.files = files;
            input.dispatchEvent(new Event('change'));
        }
    });
}

// ==================== 模态框功能 ====================

/**
 * 打开模态框
 */
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

/**
 * 关闭模态框
 */
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

/**
 * 初始化模态框
 */
function initModals() {
    // 点击遮罩关闭
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    });
    
    // ESC 键关闭
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.active').forEach(modal => {
                modal.classList.remove('active');
            });
            document.body.style.overflow = '';
        }
    });
}

// ==================== 确认删除 ====================

/**
 * 确认删除操作
 */
function confirmDelete(message = '确定要删除吗？') {
    return confirm(message);
}

/**
 * 初始化删除按钮
 */
function initDeleteButtons() {
    document.querySelectorAll('.btn-delete, [data-action="delete"]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            if (!confirmDelete(btn.dataset.message || '确定要删除吗？此操作不可恢复。')) {
                e.preventDefault();
            }
        });
    });
}

// ==================== 下载功能 ====================

/**
 * 执行随机下载
 */
function doRandomDownload() {
    const btn = document.querySelector('#download-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>🎲</span> 正在分配视频...';
        
        // 跳转下载
        window.location.href = '/download/action';
    }
}

// ==================== 表单验证 ====================

/**
 * 简单的表单验证
 */
function validateForm(form) {
    const inputs = form.querySelectorAll('[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.style.borderColor = 'var(--danger)';
            isValid = false;
        } else {
            input.style.borderColor = '';
        }
    });
    
    return isValid;
}

/**
 * 初始化表单验证
 */
function initFormValidation() {
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', (e) => {
            if (!validateForm(form)) {
                e.preventDefault();
                showToast('请填写所有必填项', 'error');
            }
        });
    });
}

// ==================== 页面加载完成后初始化 ====================

document.addEventListener('DOMContentLoaded', () => {
    // 初始化各个模块
    initUploadZone();
    initModals();
    initDeleteButtons();
    initFormValidation();
    
    // 添加按钮涟漪效果
    document.querySelectorAll('.btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            ripple.style.cssText = `
                position: absolute;
                background: rgba(255,255,255,0.3);
                border-radius: 50%;
                transform: scale(0);
                animation: ripple 0.6s linear;
                pointer-events: none;
            `;
            
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = e.clientX - rect.left - size/2 + 'px';
            ripple.style.top = e.clientY - rect.top - size/2 + 'px';
            
            this.style.position = 'relative';
            this.style.overflow = 'hidden';
            this.appendChild(ripple);
            
            setTimeout(() => ripple.remove(), 600);
        });
    });
    
    // 添加涟漪动画样式
    const style = document.createElement('style');
    style.textContent = `
        @keyframes ripple {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
});

// ==================== 导出全局函数 ====================

window.showToast = showToast;
window.openModal = openModal;
window.closeModal = closeModal;
window.confirmDelete = confirmDelete;
window.doRandomDownload = doRandomDownload;
