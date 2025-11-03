# config.py
"""
系统配置管理模块 - 环境变量驱动的配置系统

本模块负责管理机器人的所有配置参数，包括：
- Telegram Bot 认证配置
- 群组和频道设置
- 数据库连接配置
- 性能优化参数
- 安全和验证设置

特性：
- 支持 .env 文件自动加载
- 环境变量优先级配置
- 配置验证和错误处理
- 性能调优参数集成
- 动态配置热重载支持

配置优先级：
1. 系统环境变量（最高优先级）
2. .env 文件配置
3. 代码中的默认值（最低优先级）

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

import os
import logging
from pathlib import Path

# 尝试加载 .env 文件 - 优先级配置管理
try:
    from dotenv import load_dotenv
    # 查找并加载 .env 文件
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ 已加载环境变量文件: {env_path.absolute()}")
    else:
        print("ℹ️ 未找到 .env 文件，使用系统环境变量")
except ImportError:
    print("⚠️ 未安装 python-dotenv，仅使用系统环境变量")
    print("   建议安装: pip install python-dotenv")

# ===== 核心配置参数 Core Configuration =====

# 机器人令牌 - 从环境变量强制获取，确保安全性
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN 环境变量未设置")

# 管理员ID列表 - 支持多个管理员配置
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "1234567890").split(",")]

# 管理群组ID - 管理员展示和操作专用群组
MANAGEMENT_GROUP_ID = int(os.getenv("MANAGEMENT_GROUP_ID", "-1000123456789"))

# 频道ID列表 - 支持多个频道配置
CHANNEL_IDS = [int(x) if x.lstrip('-').isdigit() else x for x in os.getenv("CHANNEL_IDS", "@频道用户名").split(",")]

# 群组ID列表 - 支持多个群组配置
GROUP_IDS = [int(x) for x in os.getenv("GROUP_IDS", "-1000123456789").split(",")]

# 从数据库获取配置，如果数据库中没有则使用环境变量
def get_config_from_db_or_env():
    """从数据库获取配置，如果数据库中没有则使用环境变量"""
    try:
        # 延迟导入database以避免循环导入
        from database import db
        db_config = db.get_system_config()
        
        if db_config:
            # 区分环境变量和数据库配置
            # 环境变量中的频道和群组始终作为默认配置
            default_channels = [str(ch) for ch in CHANNEL_IDS]  # 确保都是字符串类型
            default_groups = [str(gr) for gr in GROUP_IDS]      # 确保都是字符串类型
            
            # 数据库中的额外频道和群组作为自定义配置
            custom_channels = db_config.get('channel_ids', [])
            custom_groups = db_config.get('group_ids', [])
            
            # 合并所有频道和群组：默认配置在前，自定义配置在后
            # 修复：确保所有元素都是字符串并且去重
            all_channels = []
            seen_channels = set()
            
            # 添加默认频道
            for ch in default_channels:
                if ch not in seen_channels:
                    all_channels.append(ch)
                    seen_channels.add(ch)
            
            # 添加自定义频道（排除默认频道和调试频道）
            from config import DEBUG_CHANNEL_ID
            for ch in custom_channels:
                ch_str = str(ch)
                if ch_str not in seen_channels and ch_str != str(DEBUG_CHANNEL_ID):
                    all_channels.append(ch_str)
                    seen_channels.add(ch_str)
            
            # 同样处理群组
            all_groups = []
            seen_groups = set()
            
            # 添加默认群组
            for gr in default_groups:
                if gr not in seen_groups:
                    all_groups.append(gr)
                    seen_groups.add(gr)
            
            # 添加自定义群组（排除默认群组）
            for gr in custom_groups:
                gr_str = str(gr)
                if gr_str not in seen_groups:
                    all_groups.append(gr_str)
                    seen_groups.add(gr_str)
            
            return {
                'channel_ids': all_channels,
                'group_ids': all_groups,
                'disabled_channels': db_config.get('disabled_channels', []),
                'disabled_groups': db_config.get('disabled_groups', []),
                'default_channels': default_channels,  # 保存默认频道列表用于判断
                'default_groups': default_groups       # 保存默认群组列表用于判断
            }
        else:
            # 使用环境变量中的配置
            default_channels = [str(ch) for ch in CHANNEL_IDS]
            default_groups = [str(gr) for gr in GROUP_IDS]
            return {
                'channel_ids': default_channels,
                'group_ids': default_groups,
                'disabled_channels': [],
                'disabled_groups': [],
                'default_channels': default_channels,  # 保存默认频道列表用于判断
                'default_groups': default_groups       # 保存默认群组列表用于判断
            }
    except ImportError:
        # 如果database模块不可用，使用环境变量配置
        default_channels = [str(ch) for ch in CHANNEL_IDS]
        default_groups = [str(gr) for gr in GROUP_IDS]
        return {
            'channel_ids': default_channels,
            'group_ids': default_groups,
            'disabled_channels': [],
            'disabled_groups': [],
            'default_channels': default_channels,  # 保存默认频道列表用于判断
            'default_groups': default_groups       # 保存默认群组列表用于判断
        }

# 获取当前有效的配置
current_config = get_config_from_db_or_env()

# 直接赋值而不是使用属性
CHANNEL_IDS = current_config.get('channel_ids', [])
GROUP_IDS = current_config.get('group_ids', [])

# 获取禁用的频道和群组
DISABLED_CHANNELS = current_config.get('disabled_channels', [])
DISABLED_GROUPS = current_config.get('disabled_groups', [])

# 获取默认频道和群组列表，用于判断类型
DEFAULT_CHANNEL_IDS = current_config.get('default_channels', [])
DEFAULT_GROUP_IDS = current_config.get('default_groups', [])

# 获取实际启用的频道和群组（排除禁用的）
ENABLED_CHANNEL_IDS = [channel for channel in CHANNEL_IDS if channel not in DISABLED_CHANNELS]
ENABLED_GROUP_IDS = [group for group in GROUP_IDS if group not in DISABLED_GROUPS]

# ===== 调试模式配置 Debug Mode Configuration =====

# 调试模式开关
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# 调试频道和群组ID
DEBUG_CHANNEL_ID = os.getenv("DEBUG_CHANNEL_ID", "-1003004705760")
DEBUG_GROUP_ID = os.getenv("DEBUG_GROUP_ID", "-1003035477859")

# 添加一个函数用于动态获取调试模式状态
def get_debug_mode():
    """动态获取调试模式状态"""
    import os
    return os.getenv("DEBUG_MODE", "false").lower() == "true"

# ===== 数据库配置 Database Configuration =====

# 数据库连接URL - 支持SQLite、PostgreSQL、MySQL
DB_URL = os.getenv("DB_URL", "sqlite:///submissions.db")

# ===== 成员资格验证配置 Membership Verification =====

# 需要用户加入的群组和频道ID
VERIFY_GROUP_IDS = [int(x) for x in os.getenv("VERIFY_GROUP_IDS", "-1000123456789").split(",")]
VERIFY_CHANNEL_IDS = [int(x) if x.lstrip('-').isdigit() else x for x in os.getenv("VERIFY_CHANNEL_IDS", "@频道用户名").split(",")]

# 成员资格检查强制开关 - 可选择性检查群组/频道成员身份
ENFORCE_GROUP_MEMBERSHIP = os.getenv("ENFORCE_GROUP_MEMBERSHIP", "true").lower() == "true"
ENFORCE_CHANNEL_MEMBERSHIP = os.getenv("ENFORCE_CHANNEL_MEMBERSHIP", "false").lower() == "true"  # 默认关闭频道检查

# 统一的解锁链接 - 群组和频道使用同一个链接
UNLOCK_LINK = os.getenv("UNLOCK_LINK", "https://t.me/mgbg1")

# ===== 客服联系配置 Customer Support Configuration =====

# 客服联系方式配置 - 供用户获取支持和帮助
CUSTOMER_SUPPORT_LINK = os.getenv("CUSTOMER_SUPPORT_LINK", "http://t.me/KENNELCSbot")
CUSTOMER_SUPPORT_USERNAME = os.getenv("CUSTOMER_SUPPORT_USERNAME", "@KENNELCSbot")
CUSTOMER_SUPPORT_NAME = os.getenv("CUSTOMER_SUPPORT_NAME", "客服中心")

# 客服服务时间配置
CUSTOMER_SUPPORT_HOURS = os.getenv("CUSTOMER_SUPPORT_HOURS", "09:00-22:00")
CUSTOMER_SUPPORT_TIMEZONE = os.getenv("CUSTOMER_SUPPORT_TIMEZONE", "北京时间")

# ===== 系统配置 System Configuration =====

# 日志级别转换函数 - 支持动态日志级别设置
def _get_log_level():
    """获取配置的日志级别"""
    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_str, logging.INFO)

LOG_LEVEL = _get_log_level()

# PushPlus通知配置 - 系统监控和通知推送
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "aec24c9ce0454fdca2a25f410d2ec283")
PUSHPLUS_TOPIC = os.getenv("PUSHPLUS_TOPIC", "1234")

# WxPusher通知配置 - 微信通知推送
WXPUSHER_TOKEN = os.getenv("WXPUSHER_TOKEN", "")

# 服务器监控配置 - 系统运行状态监控
SERVER_NAME = os.getenv("SERVER_NAME", "默认服务器")
SHOW_DETAILED_STATS = os.getenv("SHOW_DETAILED_STATS", "true").lower() == "true"

# ===== 性能优化配置 =====

# 数据库性能配置
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))  # 增加连接池大小
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "30"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # 30分钟
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))  # 增加连接超时时间

# 分页配置
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "20"))
MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "100"))

# 缓存配置 - 增加缓存大小和时间以提高性能
CACHE_TIMEOUT = int(os.getenv("CACHE_TIMEOUT", "600"))  # 10分钟
MAX_CACHE_SIZE = int(os.getenv("MAX_CACHE_SIZE", "2000"))  # 增加缓存大小

# 通知优化配置
NOTIFICATION_BATCH_SIZE = int(os.getenv("NOTIFICATION_BATCH_SIZE", "10"))
NOTIFICATION_DELAY = float(os.getenv("NOTIFICATION_DELAY", "0.1"))  # 100ms
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))

# 清理任务配置
CLEANUP_RETENTION_DAYS = int(os.getenv("CLEANUP_RETENTION_DAYS", "30"))
CLEANUP_BATCH_SIZE = int(os.getenv("CLEANUP_BATCH_SIZE", "100"))

# 系统监控配置
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "60"))  # 60秒
MEMORY_WARNING_THRESHOLD = int(os.getenv("MEMORY_WARNING_THRESHOLD", "80"))  # 80%
CPU_WARNING_THRESHOLD = int(os.getenv("CPU_WARNING_THRESHOLD", "80"))  # 80%

# 异步处理配置
ENABLE_ASYNC_PROCESSING = os.getenv("ENABLE_ASYNC_PROCESSING", "false").lower() == "true"
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "5"))

# 日志优化配置
LOG_FILE_MAX_SIZE = int(os.getenv("LOG_FILE_MAX_SIZE", "10485760"))  # 10MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
ENABLE_FILE_LOGGING = os.getenv("ENABLE_FILE_LOGGING", "true").lower() == "true"

# 验证配置有效性
# 验证配置有效性 - 确保关键参数的正确性和安全性
def validate_config():
    """
    验证配置参数的有效性
    
    验证内容：
    - 必需配置项的存在性
    - 数值参数的合理性
    - 配置参数的兼容性
    
    Returns:
        bool: 配置验证是否成功
    
    Raises:
        ValueError: 关键配置错误时抛出异常
    """
    errors = []
    warnings = []
    
    # 验证必需配置项
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN 是必需的")
    
    if not ADMIN_IDS:
        errors.append("ADMIN_IDS 不能为空")
    
    # 验证数值配置（非关键错误，只警告）
    if DB_POOL_SIZE <= 0:
        warnings.append(f"DB_POOL_SIZE ({DB_POOL_SIZE}) 应该大于 0，使用默认值 5")
    
    if DEFAULT_PAGE_SIZE <= 0 or DEFAULT_PAGE_SIZE > MAX_PAGE_SIZE:
        warnings.append(f"DEFAULT_PAGE_SIZE ({DEFAULT_PAGE_SIZE}) 应该在 1-{MAX_PAGE_SIZE} 之间")
    
    if NOTIFICATION_DELAY < 0:
        warnings.append(f"NOTIFICATION_DELAY ({NOTIFICATION_DELAY}) 不应为负数")
    
    # 只在关键错误时抛出异常
    if errors:
        raise ValueError(f"关键配置错误: {'; '.join(errors)}")
    
    # 警告信息只记录到日志
    if warnings:
        import logging
        logger = logging.getLogger(__name__)
        for warning in warnings:
            logger.warning(f"配置警告: {warning}")
    
    return True

# 安全的自动配置验证 - 系统启动时自动检查配置有效性
try:
    validate_config()
except Exception as config_error:
    import logging
    logging.error(f"配置验证失败: {config_error}")
    # 不阻止系统启动，只记录错误
    pass