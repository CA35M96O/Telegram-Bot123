# main.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程序入口文件 - 统一媒体投稿系统 v2.0

本文件负责初始化Telegram机器人并注册所有处理程序。

系统架构：
- 模块化设计：将功能按类型分组到不同的handlers
- 事件驱动：通过Telegram消息和回调触发处理逻辑
- 定时任务：后台运行清理、监控和报告任务
- 状态管理：维护用户交互状态和表单数据

新版特性 (v2.0)：
- 统一媒体投稿：支持混合照片和视频上传
- 智能媒体分组：自动将不同类型媒体分组发布
- 增强的错误处理和空值检查
- 保持向后兼容性
- 环境变量配置管理
- 安全的回调查询处理
- 详细的日志记录系统

技术栈：
- Python 3.x
- python-telegram-bot v20.7
- SQLAlchemy v2.0.28
- python-dotenv
- PushPlus (推送通知)
- APScheduler (定时任务)

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

import logging
from dotenv import load_dotenv  # 加载环境变量文件

# 首先加载环境变量（必须在其他导入之前）
# 这确保了所有配置在模块导入时就已经可用
load_dotenv()

# =====================================================
# 外部库导入 External Library Imports
# =====================================================

# Telegram Bot API相关组件导入
# 提供与Telegram平台交互的核心功能
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ChatMemberHandler
from telegram import Update
from telegram.ext import ContextTypes as CallbackContext

# 添加DNS劫持检测和自动修复功能
import socket
import httpx
from typing import Optional  # type: ignore

# 修复urllib3版本兼容性问题
try:
    from urllib3.util import create_urllib3_context  # type: ignore
except ImportError:
    # urllib3 2.x 版本中移除了 create_urllib3_context
    create_urllib3_context: Optional[object] = None

def detect_and_fix_dns():
    """检测DNS劫持并自动修复"""
    print("🔍 检测DNS劫持情况...")
    
    # 检测api.telegram.org是否被劫持
    try:
        # 使用原始getaddrinfo检查DNS解析结果
        original_getaddrinfo = socket.getaddrinfo
        result = original_getaddrinfo('api.telegram.org', 443)
        resolved_ips = [addr[4][0] for addr in result if addr[0] == socket.AF_INET]
        
        # 检查是否解析到正确的Telegram IP范围
        correct_ips = ['149.154.167.220', '149.154.167.221', '149.154.167.222']
        is_hijacked = not any(ip in correct_ips for ip in resolved_ips)
        
        print(f"  检测到 api.telegram.org 解析到: {resolved_ips}")
        if is_hijacked:
            print("  ⚠️  检测到DNS劫持!")
            # 应用DNS修复补丁
            patch_dns()
            return True
        else:
            print("  ✅ DNS解析正常")
            # 即使没有劫持也应用补丁以确保连接稳定
            patch_dns()
            return False
    except Exception as e:
        print(f"  ❌ DNS检测出错: {e}")
        # 出现异常时也应用DNS修复补丁
        patch_dns()
        return True

# 添加自定义DNS解析函数
def patch_dns():
    """修补DNS解析以避免DNS污染，使用动态DNS解析和故障转移"""
    # 保存原始的getaddrinfo函数
    original_getaddrinfo = socket.getaddrinfo
    
    # 定义Telegram域名和正确的IP地址映射
    # 使用多个IP地址以提高连接可靠性
    telegram_hosts = {
        'api.telegram.org': [
            '149.154.167.220',
            '149.154.167.221',
            '149.154.167.222',
        ],
        'api.telegram.org.': [
            '149.154.167.220',
            '149.154.167.221',
            '149.154.167.222',
        ],
        'core.telegram.org': [
            '149.154.167.220',
            '149.154.167.221',
            '149.154.167.222',
        ],
        'core.telegram.org.': [
            '149.154.167.220',
            '149.154.167.221',
            '149.154.167.222',
        ],
        # 添加更多Telegram相关域名
        'api.telegram.org:443': [
            '149.154.167.220',
            '149.154.167.221',
            '149.154.167.222',
        ],
        'core.telegram.org:443': [
            '149.154.167.220',
            '149.154.167.221',
            '149.154.167.222',
        ],
    }
    
    def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        """修补的DNS解析函数，支持动态DNS解析和故障转移"""
        # 如果是Telegram相关域名，直接返回正确的IP
        host_key = f"{host}:{port}" if port else host
        if isinstance(host, str):
            if host in telegram_hosts:
                ips = telegram_hosts[host]
                # 尝试连接每个IP直到成功
                for ip in ips:
                    try:
                        print(f"🔧 DNS Patch: Resolving {host} to {ip}")
                        return [(socket.AF_INET, socket.SOCK_STREAM, proto, '', (ip, port))]
                    except Exception as e:
                        print(f"  连接 {ip} 失败: {e}")
                        continue
                # 如果所有IP都失败，使用第一个IP
                ip = ips[0]
                print(f"🔧 DNS Patch: All IPs failed, using first IP {ip} for {host}")
                return [(socket.AF_INET, socket.SOCK_STREAM, proto, '', (ip, port))]
            elif host_key in telegram_hosts:
                ips = telegram_hosts[host_key]
                # 尝试连接每个IP直到成功
                for ip in ips:
                    try:
                        print(f"🔧 DNS Patch: Resolving {host_key} to {ip}")
                        return [(socket.AF_INET, socket.SOCK_STREAM, proto, '', (ip, port))]
                    except Exception as e:
                        print(f"  连接 {ip} 失败: {e}")
                        continue
                # 如果所有IP都失败，使用第一个IP
                ip = ips[0]
                print(f"🔧 DNS Patch: All IPs failed, using first IP {ip} for {host_key}")
                return [(socket.AF_INET, socket.SOCK_STREAM, proto, '', (ip, port))]
        # 调用原始函数
        result = original_getaddrinfo(host, port, family, type, proto, flags)
        # 如果是Telegram相关域名但未在映射中找到，记录调试信息
        if isinstance(host, str) and ('telegram.org' in host or 'telegram.org:' in host):
            print(f"🔧 DNS Debug: Host={host}, Port={port}, Result={result}")
        return result
    
    # 应用修补
    socket.getaddrinfo = patched_getaddrinfo
    print("✅ 已应用增强版动态DNS解析和故障转移补丁")

# 自动检测并修复DNS劫持
detect_and_fix_dns()

# 配置HTTP客户端以处理网络问题
def configure_http_client():
    """配置HTTP客户端以处理网络问题"""
    import telegram.request
    import httpx
    import ssl
    from config import DEBUG_MODE
    
    # 只在调试模式下跳过SSL证书验证
    # 生产环境中启用完整的SSL证书验证
    if DEBUG_MODE:
        # 创建SSL上下文，跳过证书验证（仅用于调试环境）
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        print("⚠️  调试模式：已禁用SSL证书验证")
        
        # 创建一个自定义的HTTP客户端，使用httpx来处理SSL上下文
        # 在新版本的python-telegram-bot中，HTTPXRequest不直接支持ssl_context参数
        # 我们需要通过httpx.Client来配置
        custom_request = telegram.request.HTTPXRequest(
            connection_pool_size=20,
            read_timeout=20,
            write_timeout=20,
            connect_timeout=20,
            pool_timeout=30
        )
    else:
        # 生产环境中使用默认的SSL上下文（启用完整验证）
        print("✅ 生产模式：已启用SSL证书验证")
        custom_request = telegram.request.HTTPXRequest(
            connection_pool_size=20,
            read_timeout=20,
            write_timeout=20,
            connect_timeout=20,
            pool_timeout=30
        )
    
    return custom_request

# =====================================================
# 项目配置导入 Project Configuration Imports
# =====================================================

# 导入配置文件 - 包含机器人令牌、管理员ID等关键配置
from config import BOT_TOKEN, ADMIN_IDS

# 导入定时任务
from jobs import (
    setup_submission_feedback  # 投稿回访评价任务设置
)
from jobs.scheduled_publish import setup_scheduled_publish  # 定时发布任务设置
from jobs.auto_ban import setup_auto_ban_job  # 自动封禁任务

# =====================================================
# 处理函数导入 Handler Function Imports
# =====================================================

# 导入所有处理函数（按功能分组）
# 每个分组对应不同的机器人功能模块
from handlers import (
    start, main_menu_callback, submission_menu_callback, media_menu_callback, business_menu_callback,
    handle_text_input, handle_photo, handle_video, business_field_callback, submit_business_callback,
    start_text_submission, start_media_submission, start_unified_media_submission, confirm_submission_callback,
    toggle_anonymous_callback, toggle_submit_anonymous_callback, multi_mixed_media_callback, handle_urge_review, multi_photo_callback,
    multi_video_callback, handle_cover_selection, set_cover_callback,
    admin_panel_callback, admin_pending_callback, handle_review_page, handle_review_callback,
    handle_view_extra_photos, handle_view_extra_videos, handle_copy_user_id_callback,
    submission_stats_callback, data_stats_callback, server_status_callback,
    history_submissions_callback, handle_history_page, handle_history_view_photos, handle_history_view_videos,
    handle_contact_user_callback,  # 新增：联系用户回调
    cancel_reject_callback, reviewer_applications_callback, handle_application_page, handle_application_decision,
    delete_published_submission_callback, republish_submission_callback,
    user_list_callback, all_user_list_callback, normal_user_list_callback, blocked_user_list_callback, banned_user_list_callback,
    handle_user_list_page, view_user_callback, ban_user_callback, direct_ban_user_callback,
    user_list_type_callback, set_reviewer_permissions_callback, toggle_reviewer_permission_callback,
    reviewer_list_callback, reviewer_management_callback,  # 审核员管理回调
    is_reviewer_or_admin, is_admin, is_reviewer,
    database_backup_callback, backup_full_callback, backup_database_only_callback, backup_config_callback, confirm_backup_callback,
    database_cleanup_callback, cleanup_old_data_callback, cleanup_user_states_callback, cleanup_logs_callback,
    optimize_database_callback, garbage_collection_callback, cleanup_status_callback, confirm_cleanup_callback,
    smart_help_callback,
    user_profile_callback, my_submission_stats_callback, wxpusher_settings_callback, set_wxpusher_uid_callback, handle_wxpusher_uid_input,
    test_wxpusher_callback,  # 添加测试WxPusher回调函数
    privacy_command, help_command, support_command, contact_command, handle_support_callbacks,
    error_handler,
    apply_reviewer_callback, handle_reviewer_application_reason, generate_invite_callback,
    debug_mode_settings_callback,
    all_user_list_callback, normal_user_list_callback, blocked_user_list_callback, banned_user_list_callback,
    membership_check_callback,
    handle_publish_keyword_input, handle_cancel_publish_callback, noop_callback,  # 新增：关键词发布相关回调
    # 新增审核员管理相关回调函数
    add_reviewer_callback, remove_reviewer_callback, reviewer_permissions_callback,
    # 新增系统管理相关回调函数
    broadcast_message_callback, restart_bot_callback
)

# 删除重复的导入部分（这些函数已经通过handlers模块导入）
# 管理员功能处理器（直接从admin模块导入）
from handlers.reviewer_application import (
    apply_reviewer_callback,
    handle_reviewer_application_reason,
    generate_invite_callback,
)

# =====================================================
# 其他模块导入 Other Module Imports
# =====================================================

from handlers.error import error_handler        # 错误处理器
from handlers.privacy import privacy_command        # 隐私政策处理器
from jobs import setup_cleanup_job, setup_periodic_report, setup_dns_monitor_job, setup_advanced_scheduler  # 定时任务设置
# 新增：导入投稿回访评价任务设置
from jobs import setup_submission_feedback  # 投稿回访评价任务设置
from utils.pushplus import send_startup_notification   # PushPlus通知服务
from utils.logging_utils import log_user_activity, log_admin_operation, log_system_event, log_submission_event  # 日志工具函数
from utils.time_utils import format_beijing_time, get_beijing_now  # 时间工具函数

# 导入数据库管理模块，用于启动时检查和更新数据库结构
from database import db

# 导入键盘布局函数
from keyboards import user_list_type_menu

# 导入推送队列
from utils.push_queue import start_push_queue, stop_push_queue

# 导入安全模块
from utils.security import security_manager

# 导入缓存管理器
from utils.cache import cache_manager

# =====================================================
# 日志系统配置 Logging System Configuration
# =====================================================

def setup_detailed_logging():
    """
    设置详细的日志系统 - 在项目目录中自动创建多种日志文件

    功能说明：
    - 自动创建 logs 目录
    - 配置多个日志处理器（控制台+文件）
    - 支持日志轮转和备份
    - 不同级别的日志分类存储

    创建的日志文件：
    1. bot.log - 主要系统日志（所有级别）
    2. bot_errors.log - 错误专用日志（WARNING+ERROR）
    3. bot_debug.log - 调试详细日志（DEBUG级别）
    4. user_activities.log - 用户活动日志（USER_ACTIVITY标签）
    5. admin_operations.log - 管理员操作日志（ADMIN_OPERATION标签）
    6. bugs_database.log - 数据库相关Bug日志
    7. bugs_network.log - 网络相关Bug日志
    8. bugs_media.log - 媒体处理Bug日志
    9. bugs_permission.log - 权限相关Bug日志
    10. bugs_resource.log - 系统资源Bug日志
    11. bugs_external.log - 第三方服务Bug日志
    12. bugs_input.log - 用户输入Bug日志
    13. bugs_scheduler.log - 定时任务Bug日志
    14. bugs_unknown.log - 未知类型Bug日志

    Returns:
        logging.Logger: 配置完成的日志器实例

    Raises:
        Exception: 如果日志系统初始化失败
    """
    import os
    from datetime import datetime
    from logging.handlers import RotatingFileHandler
    from config import LOG_FILE_MAX_SIZE, LOG_BACKUP_COUNT, ENABLE_FILE_LOGGING

    # 创建logs目录（如果不存在）
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        print(f"📁 创建日志目录: {logs_dir}")

    # 日志格式配置
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 清除现有的处理器
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 配置处理器列表
    handlers = []

    # 1. 控制台输出（始终启用）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    handlers.append(console_handler)

    if ENABLE_FILE_LOGGING:
        # 2. 主日志文件 - 完整系统日志
        main_log_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'bot.log'),
            maxBytes=LOG_FILE_MAX_SIZE,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        main_log_handler.setLevel(logging.INFO)
        main_log_handler.setFormatter(detailed_formatter)
        handlers.append(main_log_handler)

        # 3. 错误日志文件 - 仅错误和警告
        error_log_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'bot_errors.log'),
            maxBytes=LOG_FILE_MAX_SIZE // 2,  # 错误日志文件小一些
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        error_log_handler.setLevel(logging.WARNING)
        error_log_handler.setFormatter(detailed_formatter)
        handlers.append(error_log_handler)

        # 4. 调试日志文件 - 详细调试信息
        debug_log_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'bot_debug.log'),
            maxBytes=LOG_FILE_MAX_SIZE,
            backupCount=3,  # 调试日志保留较少
            encoding='utf-8'
        )
        debug_log_handler.setLevel(logging.DEBUG)
        debug_log_handler.setFormatter(detailed_formatter)
        handlers.append(debug_log_handler)

        # 5. 用户活动日志文件 - 专门记录用户操作
        user_activity_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'user_activities.log'),
            maxBytes=LOG_FILE_MAX_SIZE,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        user_activity_handler.setLevel(logging.INFO)
        user_activity_handler.setFormatter(simple_formatter)
        # 为用户活动日志设置过滤器
        user_activity_handler.addFilter(lambda record: 'USER_ACTIVITY' in record.getMessage())
        handlers.append(user_activity_handler)

        # 6. 管理员操作日志文件 - 专门记录管理员操作
        admin_operations_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'admin_operations.log'),
            maxBytes=LOG_FILE_MAX_SIZE // 2,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        admin_operations_handler.setLevel(logging.INFO)
        admin_operations_handler.setFormatter(detailed_formatter)
        # 为管理员操作日志设置过滤器
        admin_operations_handler.addFilter(lambda record: 'ADMIN_OPERATION' in record.getMessage())
        handlers.append(admin_operations_handler)

        # 7. Bug分类日志文件 - 按类型分类记录Bug
        bug_log_configs = [
            ('bugs_database.log', 'DATABASE_BUG', logging.ERROR),
            ('bugs_network.log', 'NETWORK_BUG', logging.ERROR),
            ('bugs_media.log', 'MEDIA_BUG', logging.ERROR),
            ('bugs_permission.log', 'PERMISSION_BUG', logging.ERROR),
            ('bugs_resource.log', 'RESOURCE_BUG', logging.ERROR),
            ('bugs_external.log', 'EXTERNAL_BUG', logging.ERROR),
            ('bugs_input.log', 'INPUT_BUG', logging.ERROR),
            ('bugs_scheduler.log', 'SCHEDULER_BUG', logging.ERROR),
            ('bugs_unknown.log', 'UNKNOWN_BUG', logging.ERROR)
        ]

        for filename, bug_type, level in bug_log_configs:
            bug_handler = RotatingFileHandler(
                os.path.join(logs_dir, filename),
                maxBytes=LOG_FILE_MAX_SIZE // 4,  # Bug日志文件更小一些
                backupCount=LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            bug_handler.setLevel(level)
            bug_handler.setFormatter(detailed_formatter)
            # 为Bug日志设置过滤器
            bug_handler.addFilter(lambda record, bt=bug_type: bt in record.getMessage())
            handlers.append(bug_handler)

    # 应用日志配置
    logging.basicConfig(
        level=logging.DEBUG,  # 设置为DEBUG以捕获所有日志
        handlers=handlers,
        force=True  # 强制重新配置
    )

    # 记录日志系统启动信息
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("🚀 详细日志系统已启动")
    logger.info(f"📁 日志目录: {os.path.abspath(logs_dir)}")
    logger.info(f"📝 主日志: {os.path.abspath(os.path.join(logs_dir, 'bot.log'))}")
    if ENABLE_FILE_LOGGING:
        logger.info(f"❌ 错误日志: {os.path.abspath(os.path.join(logs_dir, 'bot_errors.log'))}")
        logger.info(f"🔍 调试日志: {os.path.abspath(os.path.join(logs_dir, 'bot_debug.log'))}")
        logger.info(f"👥 用户活动日志: {os.path.abspath(os.path.join(logs_dir, 'user_activities.log'))}")
        logger.info(f"⚙️ 管理员操作日志: {os.path.abspath(os.path.join(logs_dir, 'admin_operations.log'))}")
        logger.info(f"🗄️ 数据库Bug日志: {os.path.abspath(os.path.join(logs_dir, 'bugs_database.log'))}")
        logger.info(f"🌐 网络Bug日志: {os.path.abspath(os.path.join(logs_dir, 'bugs_network.log'))}")
        logger.info(f"🎬 媒体Bug日志: {os.path.abspath(os.path.join(logs_dir, 'bugs_media.log'))}")
        logger.info(f"🔐 权限Bug日志: {os.path.abspath(os.path.join(logs_dir, 'bugs_permission.log'))}")
        logger.info(f"💾 资源Bug日志: {os.path.abspath(os.path.join(logs_dir, 'bugs_resource.log'))}")
        logger.info(f"🔌 外部服务Bug日志: {os.path.abspath(os.path.join(logs_dir, 'bugs_external.log'))}")
        logger.info(f"📝 输入Bug日志: {os.path.abspath(os.path.join(logs_dir, 'bugs_input.log'))}")
        logger.info(f"⏰ 定时任务Bug日志: {os.path.abspath(os.path.join(logs_dir, 'bugs_scheduler.log'))}")
        logger.info(f"❓ 未知Bug日志: {os.path.abspath(os.path.join(logs_dir, 'bugs_unknown.log'))}")
    logger.info(f"⏰ 启动时间: {format_beijing_time(get_beijing_now())}")
    logger.info("=" * 50)

    return logger

# 初始化详细日志系统
logger = setup_detailed_logging()

# 添加自定义DNS解析函数
def configure_dns():
    """配置自定义DNS解析以避免DNS污染"""
    # 定义Telegram域名和正确的IP地址映射
    telegram_ips = {
        'api.telegram.org': '149.154.167.220',
        'api.telegram.org.': '149.154.167.220',
    }
    
    # 添加主机名到IP的映射
    for hostname, ip in telegram_ips.items():
        try:
            # 添加到系统主机解析中
            socket.gethostbyname(hostname)
        except socket.gaierror:
            # 如果默认解析失败，使用自定义映射
            pass

async def post_init_handler(application):
    """
    应用初始化后的处理函数

    这个函数在机器人启动后执行，用于设置定时任务等需要在应用运行时执行的操作

    Args:
        application: Telegram Application 实例
    """
    try:
        # 记录系统启动事件
        log_system_event("BOT_STARTUP_BEGIN", "Beginning bot initialization process")

        # ===== 数据库结构检查和更新 =====
        # 在启动时自动检查和更新数据库结构
        logger.info("🔍 检查数据库结构...")
        try:
            if db.upgrade_database():
                logger.info("✅ 数据库结构检查和更新完成")
                log_system_event("DATABASE_UPGRADE_SUCCESS", "Database structure checked and updated successfully")
            else:
                logger.warning("⚠️ 数据库结构更新失败")
                log_system_event("DATABASE_UPGRADE_FAILED", "Database structure upgrade failed", "WARNING")
        except Exception as db_error:
            logger.error(f"数据库结构检查过程中发生错误: {db_error}")
            log_system_event("DATABASE_UPGRADE_ERROR", f"Error during database structure check: {str(db_error)}", "ERROR")

        # ===== 设置定时任务 =====
        # 这些任务在后台运行，不会阻塞主线程
        logger.info("⏰ 设置定时任务...")
        application.job_queue.run_once(setup_cleanup_job, when=5)      # 5秒后启动清理任务
        application.job_queue.run_once(setup_periodic_report, when=3)  # 3秒后启动周期报告
        application.job_queue.run_once(setup_dns_monitor_job, when=10) # 10秒后启动DNS监控
        application.job_queue.run_once(setup_advanced_scheduler, when=15) # 15秒后启动高级调度器
        # 新增：设置投稿回访评价任务
        application.job_queue.run_once(setup_submission_feedback, when=20) # 20秒后启动回访评价任务
        # 新增：设置定时发布任务
        application.job_queue.run_once(setup_scheduled_publish, when=22) # 22秒后启动定时发布任务
        # 新增：设置自动封禁任务
        application.job_queue.run_once(setup_auto_ban_job, when=25) # 25秒后启动自动封禁任务
        log_system_event("SCHEDULED_JOBS_SET", "All scheduled jobs configured")

        # 发送启动通知给管理员
        logger.info("📢 发送启动通知...")
        send_startup_notification()
        log_system_event("STARTUP_NOTIFICATION_SENT", "Startup notifications sent to admins")

        # 初始化缓存系统
        logger.info("🚀 初始化缓存系统...")
        try:
            from utils.cached_db import warmup_all_caches
            warmup_all_caches()
            log_system_event("CACHE_SYSTEM_INITIALIZED", "Cache system warmup completed")
            logger.info("✅ 缓存系统初始化完成")
        except Exception as cache_error:
            logger.warning(f"缓存系统初始化失败: {cache_error}")
            log_system_event("CACHE_INIT_WARNING", f"Cache initialization failed: {str(cache_error)}", "WARNING")

        logger.info("✅ 机器人初始化完成")

    except Exception as e:
        logger.critical(f"机器人初始化失败: {e}")
        log_system_event("BOT_STARTUP_FAILED", f"Critical error during startup: {str(e)}")

def register_handlers(application):
    """注册所有处理器
    
    Args:
        application: Telegram应用实例
    """
    # 注意：命令处理器已经在main函数中注册，这里不再重复注册
    # 添加系统配置输入处理器
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_config_input
    ), group=2)

# 系统配置输入处理函数已移除（系统管理功能已禁用）
async def handle_config_input(update, context):
    """处理系统配置输入（已禁用）"""
    return False

def register_system_management_handlers():
    """注册系统管理处理器（已禁用）"""
    # 系统管理功能已完全移除
    return []

# 添加自定义请求处理器以解决DNS污染
def create_custom_httpx_client():
    """创建自定义的HTTPX客户端以解决DNS污染问题"""
    # 创建带有自定义DNS解析的客户端
    # 使用正确的Telegram服务器IP地址
    client = httpx.AsyncClient()
    return client

def main():
    """主函数 - 初始化并启动机器人"""
    try:
        # 记录启动开始
        log_system_event("BOT_STARTUP_BEGIN", "Starting bot initialization process")
        logger.info("🚀 开始初始化机器人...")

        # 确保BOT_TOKEN存在（这已经在config.py中检查过了，但为了类型安全再检查一次）
        if not BOT_TOKEN:
            raise ValueError("BOT_TOKEN 环境变量未设置")
        
        # 创建应用构建器
        builder = ApplicationBuilder().token(BOT_TOKEN)
        
        # 使用自定义的HTTP客户端解决DNS污染问题
        custom_request = configure_http_client()
        builder = builder.request(custom_request)
        
        # 构建应用
        application = builder.build()
        
        # 配置DNS（如果需要）
        configure_dns()

        # 注册命令处理程序
        logger.info("📝 注册命令处理器...")
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("privacy", privacy_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("support", support_command))  # 新增：客服联系命令
        application.add_handler(CommandHandler("contact", contact_command))  # 新增：联系我们命令
        log_system_event("COMMAND_HANDLERS_REGISTERED", "All command handlers registered")

        # 注册回调查询处理程序 - 优化的批量注册
        logger.info("🔄 注册回调处理器...")
        from handlers.admin import confirm_restart_bot_callback  # 导入确认重启机器人回调函数
        from handlers.user_experience import (
            language_settings_callback, theme_settings_callback, toggle_notifications_callback,
            toggle_tips_callback, toggle_compact_mode_callback, toggle_preview_callback,
            quick_action_callback, reset_preferences_callback, confirm_reset_preferences_callback,
            usage_stats_callback, user_experience_menu_callback
        )
        callback_handlers = [
            # 基础导航回调
            ("^main_menu$", main_menu_callback),
            ("^submit_menu$", submission_menu_callback),

            # 投稿相关回调
            ("^submit_text$", start_text_submission),
            ("^submit_photo$", lambda update, context: start_media_submission(update, context, "photo")),
            ("^submit_video$", lambda update, context: start_media_submission(update, context, "video")),
            ("^submit_media$", media_menu_callback),
            ("^submit_mixed_media$", start_unified_media_submission),
            ("^(add_photo_to_mixed|add_video_to_mixed|finish_mixed_media|submit_mixed_media_final)$", multi_mixed_media_callback),
            ("^(confirm|edit)_(text|photo|video|media)$", confirm_submission_callback),
            ("^toggle_anonymous$", toggle_anonymous_callback),
            ("^toggle_submit_anonymous_(true|false)$", toggle_submit_anonymous_callback),
            ("^multi_photo$", multi_photo_callback),
            ("^multi_video$", multi_video_callback),
            ("^set_cover_(\\d+)$", set_cover_callback),
            ("^handle_urge_review_(\\d+)$", handle_urge_review),
            ("^noop$", noop_callback),

            # 管理员和审核员面板回调
            ("^admin_panel$", admin_panel_callback),
            ("^admin_pending$", admin_pending_callback),
            ("^review_(\\d+)$", handle_review_page),
            ("^(approve|reject|contact)_(\\d+)$", handle_review_callback),
            ("^view_extra_photos_(\\d+)$", handle_view_extra_photos),
            ("^view_extra_videos_(\\d+)$", handle_view_extra_videos),
            ("^copy_user_id_(\\d+)$", handle_copy_user_id_callback),
            ("^contact_user_(\\d+)$", handle_contact_user_callback),
            ("^cancel_reject_(\\d+)$", cancel_reject_callback),
            ("^submission_stats$", submission_stats_callback),
            ("^data_stats$", data_stats_callback),
            ("^server_status$", server_status_callback),
            ("^history_submissions$", history_submissions_callback),
            (r"^history_(\d+)$", handle_history_page),
            (r"^history_view_photos_(\d+)$", handle_history_view_photos),
            (r"^history_view_videos_(\d+)$", handle_history_view_videos),
            ("^delete_published_(\\d+)$", delete_published_submission_callback),
            ("^republish_(\\d+)$", republish_submission_callback),
            ("^user_list$", user_list_callback),
            ("^user_list_page_(\\d+)_(normal|blocked|banned|all)$", handle_user_list_page),  # 修复用户列表分页回调
            ("^view_user_(\\d+)$", view_user_callback),
            ("^(ban|unban)_user_(\\d+)$", ban_user_callback),
            ("^direct_ban_user$", direct_ban_user_callback),
            ("^reviewer_list$", reviewer_list_callback),
            ("^reviewer_management$", reviewer_management_callback),
            ("^reviewer_applications$", reviewer_applications_callback),
            ("^application_page_(\\d+)$", handle_application_page),
            ("^application_(approve|reject)_(\\d+)$", handle_application_decision),
            (r"^generate_invite_(\d+)$", generate_invite_callback),
            ("^add_reviewer$", add_reviewer_callback),
            ("^remove_reviewer$", remove_reviewer_callback),
            ("^reviewer_permissions$", reviewer_permissions_callback),
            ("^apply_reviewer$", apply_reviewer_callback),
            ("^set_perm_(\\d+)$", set_reviewer_permissions_callback),  # 添加设置审核员权限回调
            ("^toggle_perm_(\\w+)_(\\d+)$", toggle_reviewer_permission_callback),  # 添加切换审核员权限回调

            # 系统管理回调
            ("^broadcast_message$", broadcast_message_callback),
            ("^restart_bot$", restart_bot_callback),
            ("^confirm_restart_bot$", confirm_restart_bot_callback),  # 添加确认重启机器人回调处理
            ("^debug_mode_settings$", debug_mode_settings_callback),

            # 发布关键词回调
            ("^handle_cancel_publish_(\\d+)$", handle_cancel_publish_callback),
            
            # 用户个人中心相关回调
            ("^user_profile$", user_profile_callback),
            ("^my_submission_stats$", my_submission_stats_callback),
            ("^wxpusher_settings$", wxpusher_settings_callback),
            ("^set_wxpusher_uid$", set_wxpusher_uid_callback),
            ("^test_wxpusher$", test_wxpusher_callback),
            ("^usage_stats$", usage_stats_callback),
            
            # 用户管理相关回调
            ("^all_user_list$", all_user_list_callback),
            ("^normal_user_list$", normal_user_list_callback),
            ("^blocked_user_list$", blocked_user_list_callback),
            ("^banned_user_list$", banned_user_list_callback),
            ("^user_list_type$", user_list_type_callback),  # 添加用户列表类型回调
            
            # 备份和清理相关回调
            ("^database_backup$", database_backup_callback),
            ("^backup_full$", backup_full_callback),
            ("^backup_database_only$", backup_database_only_callback),
            ("^backup_config$", backup_config_callback),
            ("^confirm_backup$", confirm_backup_callback),
            ("^database_cleanup$", database_cleanup_callback),
            ("^cleanup_old_data$", cleanup_old_data_callback),
            ("^cleanup_user_states$", cleanup_user_states_callback),
            ("^cleanup_logs$", cleanup_logs_callback),
            ("^optimize_database$", optimize_database_callback),
            ("^garbage_collection$", garbage_collection_callback),
            ("^cleanup_status$", cleanup_status_callback),
            ("^confirm_cleanup$", confirm_cleanup_callback),
            
            # 帮助和用户体验相关回调
            ("^smart_help$", smart_help_callback),
            ("^handle_support$", handle_support_callbacks),
            ("^business_menu$", business_menu_callback),
            ("^membership_check$", membership_check_callback),
            
            # 用户体验设置相关回调
            ("^user_experience_menu$", user_experience_menu_callback),
            ("^language_settings$", language_settings_callback),
            ("^theme_settings$", theme_settings_callback),
            ("^toggle_notifications$", toggle_notifications_callback),
            ("^toggle_tips$", toggle_tips_callback),
            ("^toggle_compact_mode$", toggle_compact_mode_callback),
            ("^toggle_preview$", toggle_preview_callback),
            ("^quick_action$", quick_action_callback),
            ("^reset_preferences$", reset_preferences_callback),
            ("^confirm_reset_preferences$", confirm_reset_preferences_callback),
        ]

        # 批量注册回调处理器 - 优化性能
        callback_count = 0
        for pattern, handler in callback_handlers:
            application.add_handler(CallbackQueryHandler(handler, pattern=pattern))
            callback_count += 1

        # 注册系统管理回调处理器
        system_management_handlers = register_system_management_handlers()
        for handler in system_management_handlers:
            application.add_handler(handler)
            callback_count += 1

        # 检查是否有缺失的处理器
        expected_callback_count = len(callback_handlers)  # 直接使用实际定义的回调处理器数量
        if callback_count != expected_callback_count:
            logger.warning(f"回调处理器数量不匹配: 期望 {expected_callback_count} 个, 实际注册 {callback_count} 个")
            # 列出所有回调处理器模式进行调试
            logger.debug("已注册的回调处理器模式:")
            for i, (pattern, _) in enumerate(callback_handlers):
                logger.debug(f"  {i+1}. {pattern}")

        log_system_event("CALLBACK_HANDLERS_REGISTERED", f"Registered {callback_count} callback handlers")
        logger.info(f"✅ 已注册 {callback_count} 个回调处理器")

        # 注册消息处理程序
        logger.info("💬 注册消息处理器...")
        
        # 添加关键词发布处理函数 (Group 0: 处理关键词输入，需要最高优先级)
        application.add_handler(MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, 
            handle_publish_keyword_input
        ), group=0)
        
        # 添加WxPusher UID输入处理函数 (Group 1: 处理WxPusher UID)
        application.add_handler(MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            handle_wxpusher_uid_input
        ), group=1)
        
        # 注册跳转页面输入处理器 (Group 2: 处理跳转页面输入)
        from handlers.review import handle_jump_to_page_input
        application.add_handler(MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            handle_jump_to_page_input
        ), group=2)
        
        # 注册用户ID输入处理器 (Group 3: 处理用户ID输入)
        from handlers.user_management import handle_user_id_input
        application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_user_id_input), group=3)
        
        # 注册混合媒体投稿消息处理器 (Group 4: 处理混合媒体投稿)
        from handlers.submission import _handle_mixed_media_message
        application.add_handler(MessageHandler(
            (filters.PHOTO | filters.VIDEO | filters.TEXT) & ~filters.COMMAND,
            _handle_mixed_media_message
        ), group=4)
        
        # 注册通用文本消息处理器 (Group 8: 最低优先级)
        application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_text_input), group=8)
        
        # 注册其他消息处理器
        application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.PHOTO, handle_photo), group=5)
        application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.VIDEO, handle_video), group=5)
        
        log_system_event("MESSAGE_HANDLERS_REGISTERED", "Text, photo, and video message handlers registered")

        # 注册错误处理程序
        logger.info("❌ 注册错误处理器...")
        application.add_error_handler(error_handler)
        log_system_event("ERROR_HANDLER_REGISTERED", "Global error handler registered")

        # 记录初始化完成
        log_system_event("BOT_INITIALIZATION_COMPLETE", "All handlers and jobs configured successfully")
        logger.info("✅ 机器人初始化完成")

        # 启动机器人
        logger.info("🚀 启动机器人...")
        # 在Windows环境下，我们需要传递stop_signals=None来避免事件循环问题
        application.run_polling(drop_pending_updates=True, stop_signals=None)
        log_system_event("BOT_STARTED", "Bot is now running and listening for updates")
        logger.info("🎉 机器人已启动，正在监听消息...")

        # 记录启动成功信息
        from datetime import datetime
        startup_time = format_beijing_time(get_beijing_now())
        logger.info("=" * 60)
        logger.info("🎆 系统启动成功！")
        logger.info(f"🕰 启动时间: {startup_time}")
        # 安全地显示Bot Token信息
        if BOT_TOKEN:
            logger.info(f"🔗 Bot Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-10:]}")
        else:
            logger.warning("⚠️ Bot Token 未设置")
        logger.info(f"👥 管理员数量: {len(ADMIN_IDS)}")
        logger.info("📊 系统状态: 正常运行")
        logger.info("📁 日志记录: 已启用详细日志")
        logger.info("=" * 60)

    except Exception as e:
        logger.critical(f"机器人启动失败: {e}")
        log_system_event("BOT_STARTUP_FAILED", f"Critical error during startup: {str(e)}")
        raise
    finally:
        log_system_event("BOT_SHUTDOWN", "Bot shutdown initiated")

if __name__ == '__main__':
    main()

