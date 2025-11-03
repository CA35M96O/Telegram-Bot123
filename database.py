# database.py
"""
数据库管理模块 - SQLAlchemy ORM 数据库操作封装

本模块提供了完整的数据库操作接口，包括：
- 数据模型定义（用户、投稿、状态等）
- 数据库连接管理和会话处理
- CRUD操作封装（增删改查）
- 索引优化和性能调优
- 数据库迁移和版本管理

技术特性：
- 使用 SQLAlchemy 2.0.28 ORM
- 支持连接池和会话管理
- 自动创建表和索引
- 支持事务处理和上下文管理
- 安全的数据验证和错误处理

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

# =====================================================
# 外部库导入 External Library Imports
# =====================================================

# SQLAlchemy 核心组件
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func, text
from sqlalchemy import inspect
from sqlalchemy.pool import QueuePool

# Python 标准库
import json
import logging
import re
from datetime import datetime, timedelta
from contextlib import contextmanager

# 导入时间工具
from utils.time_utils import get_beijing_now

# 项目配置 - 延迟导入以避免循环导入
def get_config_values():
    """延迟获取配置值以避免循环导入"""
    try:
        from config import DB_URL, LOG_LEVEL, DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_RECYCLE
        return DB_URL, LOG_LEVEL, DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_RECYCLE
    except ImportError:
        # 默认配置值
        return (
            "sqlite:///submissions.db",
            logging.INFO,
            10,
            20,
            3600
        )

# 获取配置值
DB_URL, LOG_LEVEL, DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_RECYCLE = get_config_values()

# =====================================================
# 日志配置 Logging Configuration
# =====================================================

# 设置数据库模块的日志配置
# 使用与主程序一致的日志级别和格式
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=LOG_LEVEL
)
logger = logging.getLogger(__name__)

# =====================================================
# 数据模型定义 Data Model Definitions
# =====================================================

# 创建 SQLAlchemy 声明式基类
# 所有数据模型都将继承这个基类
Base = declarative_base()

class User(Base):
    """
    用户数据模型 - 存储Telegram用户的基本信息
    
    表功能：
    - 记录用户的Telegram基本信息
    - 跟踪用户的首次和最后交互时间
    
    数据字段说明：
    - user_id: Telegram用户ID（主键）
    - username: 用户名（可为空）
    - first_name: 名字（必填）
    - last_name: 姓氏（可为空）
    - is_bot: 是否为机器人账户
    - language_code: 用户语言代码
    - last_interaction: 最后交互时间（自动更新）
    - first_interaction: 首次交互时间（不变）
    """
    __tablename__ = 'users'
    
    # 主键 - 使用Telegram用户ID作为唯一标识符
    user_id = Column(Integer, primary_key=True, comment='用户的Telegram ID')
    
    # 基本信息字段
    username = Column(String(100), comment='用户名（@username）')
    first_name = Column(String(100), comment='用户的名字')
    last_name = Column(String(100), comment='用户的姓氏')
    
    # 用户类型和设置
    is_bot = Column(Boolean, default=False, comment='是否为机器人账户')
    language_code = Column(String(10), comment='用户语言代码（如zh-cn）')
    
    # 新增：WxPusher UID 用于推送通知
    wxpusher_uid = Column(String(100), comment='WxPusher UID 用于接收微信推送通知')
    
    # 时间跟踪字段
    last_interaction = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(),
        comment='最后交互时间（自动更新）'
    )
    first_interaction = Column(
        DateTime(timezone=True), 
        server_default=func.now(),
        comment='首次交互时间（创建时设定）'
    )
    
    # 用户状态字段
    bot_blocked = Column(
        Boolean, 
        default=False,
        comment='用户是否删除或屏蔽了机器人'
    )
    is_banned = Column(
        Boolean,
        default=False,
        comment='用户是否被封禁'
    )
    is_reviewer = Column(
        Boolean,
        default=False,
        comment='用户是否为审核员'
    )

class Submission(Base):
    """投稿数据模型"""
    __tablename__ = 'submissions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # 投稿类型: text, photo, video
    content = Column(Text, nullable=False)     # 投稿内容
    file_id = Column(String(200))              # 媒体文件ID
    file_ids = Column(Text, default='[]')      # 多图文件ID列表
    file_types = Column(Text, default='[]')    # 文件类型列表，对应file_ids
    tags = Column(Text, default='[]')          # 标签字段
    status = Column(String(20), default='pending')  # 状态: pending, approved, rejected
    category = Column(String(20), default='submission')  # 分类: submission, business
    anonymous = Column(Boolean, default=False)  # 是否匿名
    cover_index = Column(Integer, default=0)    # 多图封面索引
    reject_reason = Column(Text)                # 拒绝原因
    handled_by = Column(Integer)                # 处理此投稿的管理员ID
    handled_at = Column(DateTime(timezone=True))  # 处理时间
    timestamp = Column(DateTime(timezone=True), server_default=func.now())  # 投稿时间
    # 新增：存储已发布消息的ID
    published_message_id = Column(String(100))  # 频道中发布的消息ID（兼容旧版本）
    published_channel_message_ids = Column(Text, default='[]')  # 多个频道中发布的消息ID列表
    published_group_message_ids = Column(Text, default='[]')  # 群组中发布的消息ID列表
    # 新增：回访评价相关字段
    feedback_sent = Column(Boolean, default=False)  # 是否已发送回访评价
    feedback_sent_at = Column(DateTime(timezone=True))  # 回访评价发送时间
    # 新增：定时发布相关字段
    scheduled_publish_time = Column(DateTime(timezone=True))  # 定时发布时间
    custom_keyword = Column(String(100))  # 自定义关键词
    
    # 添加索引以提高查询性能
    __table_args__ = (
        Index('idx_submissions_status', 'status'),
        Index('idx_submissions_user_id', 'user_id'),
        Index('idx_submissions_timestamp', 'timestamp'),
        Index('idx_submissions_category', 'category'),
        Index('idx_submissions_handled_by', 'handled_by'),
        Index('idx_submissions_scheduled_publish_time', 'scheduled_publish_time'),
    )

class UserState(Base):
    """用户状态数据模型"""
    __tablename__ = 'user_states'
    
    user_id = Column(Integer, primary_key=True)
    state = Column(String(50), nullable=False)  # 用户当前状态
    data = Column(Text, default='{}')           # 状态数据
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 添加索引以提高查询性能
    __table_args__ = (
        Index('idx_user_states_timestamp', 'timestamp'),
    )

class ReviewerApplication(Base):
    """审核员申请数据模型"""
    __tablename__ = 'reviewer_applications'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(100), nullable=False)
    reason = Column(Text)  # 申请理由
    status = Column(String(20), default='pending')  # 状态: pending, approved, rejected
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    handled_by = Column(Integer)  # 处理此申请的管理员ID
    handled_at = Column(DateTime(timezone=True))  # 处理时间
    invite_link = Column(String(500))  # 生成的邀请链接
    # 新增：审核员权限设置
    permissions = Column(Text, default='{}')  # 审核员权限设置，JSON格式存储
    
    # 添加索引以提高查询性能
    __table_args__ = (
        Index('idx_reviewer_status', 'status'),
        Index('idx_reviewer_user_id', 'user_id'),
    )

class Tag(Base):
    """标签数据模型"""
    __tablename__ = 'tags'
    
    name = Column(String(50), primary_key=True)  # 标签名称作为主键
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    usage_count = Column(Integer, default=0)  # 使用次数统计

class BanRecord(Base):
    """封禁记录数据模型"""
    __tablename__ = 'ban_records'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)  # 被封禁的用户ID
    banned_by = Column(Integer, nullable=False)  # 封禁者ID
    reason = Column(Text)  # 封禁原因
    ban_type = Column(String(20), default='temporary')  # 封禁类型: temporary, permanent
    ban_start = Column(DateTime(timezone=True), server_default=func.now())  # 封禁开始时间
    ban_end = Column(DateTime(timezone=True))  # 封禁结束时间（临时封禁时使用）
    unbanned_by = Column(Integer)  # 解封者ID
    unbanned_at = Column(DateTime(timezone=True))  # 解封时间
    
    # 添加索引以提高查询性能
    __table_args__ = (
        Index('idx_ban_records_user_id', 'user_id'),
        Index('idx_ban_records_ban_type', 'ban_type'),
        Index('idx_ban_records_ban_start', 'ban_start'),
    )

class SystemConfig(Base):
    """系统配置数据模型"""
    __tablename__ = 'system_config'
    
    id = Column(Integer, primary_key=True)
    channel_ids = Column(Text, default='')  # 频道ID列表
    group_ids = Column(Text, default='')    # 群组ID列表
    disabled_channels = Column(Text, default='')  # 禁用的频道ID列表
    disabled_groups = Column(Text, default='')    # 禁用的群组ID列表

class DatabaseManager:
    """数据库管理类"""
    
    def __init__(self, db_url=DB_URL):
        """初始化数据库连接 - 安全版本
        
        增加了安全检查和错误处理，确保项目正常运行
        
        Args:
            db_url: 数据库连接URL
        """
        try:
            # 获取数据库连接池配置
            try:
                from config import DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_RECYCLE, DB_POOL_TIMEOUT
            except ImportError:
                # 使用默认值
                DB_POOL_SIZE = 10
                DB_MAX_OVERFLOW = 20
                DB_POOL_RECYCLE = 3600
                DB_POOL_TIMEOUT = 30
            
            # 优化连接池配置
            self.engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=DB_POOL_SIZE,
                max_overflow=DB_MAX_OVERFLOW,
                pool_recycle=DB_POOL_RECYCLE,
                pool_pre_ping=True,
                pool_timeout=DB_POOL_TIMEOUT  # 添加连接超时配置
            )
            self.Session = sessionmaker(bind=self.engine)
            
            # 逐步初始化，确保各步骤的稳定性
            self._create_tables()
            self._check_and_add_missing_columns()
            self._create_ban_records_table()
            
            # 索引优化（在安全模式下执行）
            try:
                self._create_indexes()
            except Exception as e:
                logger.warning(f"索引优化失败，系统仍可正常运行: {e}")
            
            logger.info(f"数据库已成功初始化: {db_url}")
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            # 在关键错误时，尝试使用基本配置
            self._fallback_initialization(db_url)
    
    def _create_tables(self):
        """创建数据库表"""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("数据库表已创建/验证")
        except Exception as e:
            logger.error(f"创建表失败: {e}")
    
    def _create_indexes(self):
        """创建关键索引以提高查询性能"""
        try:
            with self.session_scope() as session:
                # 定义索引映射表以便于管理
                indexes = {
                    'submissions': [
                        ('idx_submissions_status', 'status'),
                        ('idx_submissions_user_id', 'user_id'),
                        ('idx_submissions_timestamp', 'timestamp'),
                        ('idx_submissions_category', 'category'),
                        ('idx_submissions_handled_by', 'handled_by')
                    ],
                    'users': [
                        ('idx_users_last_interaction', 'last_interaction')
                    ],
                    'reviewer_applications': [
                        ('idx_reviewer_status', 'status'),
                        ('idx_reviewer_user_id', 'user_id')
                    ],
                    'user_states': [
                        ('idx_user_states_timestamp', 'timestamp')
                    ]
                }
                
                # 批量创建索引
                for table_name, table_indexes in indexes.items():
                    for index_name, column_name in table_indexes:
                        try:
                            if not inspect(self.engine).has_index(table_name, index_name):
                                session.execute(text(f'CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})'))
                        except Exception as e:
                            logger.warning(f"创建索引 {index_name} 失败: {e}")
                
                session.commit()
            logger.info("数据库索引已优化")
        except Exception as e:
            logger.error(f"创建索引失败: {e}")
    
    def _check_and_add_missing_columns(self):
        """检查并添加缺失的列"""
        try:
            inspector = inspect(self.engine)
            with self.session_scope() as session:
                # 检查并创建 tags 表
                if 'tags' not in inspector.get_table_names():
                    Base.metadata.tables['tags'].create(self.engine)
                    logger.info("创建 tags 表")
                
                # 检查 users 表
                if 'users' in inspector.get_table_names():
                    columns = [column['name'] for column in inspector.get_columns('users')]
                    
                    # 新增：检查并添加 wxpusher_uid 列
                    if 'wxpusher_uid' not in columns:
                        logger.info("添加 wxpusher_uid 列...")
                        session.execute(text('ALTER TABLE users ADD COLUMN wxpusher_uid VARCHAR(100)'))
                    
                    # 检查并添加 first_interaction 列
                    if 'first_interaction' not in columns:
                        logger.info("添加 first_interaction 列...")
                        session.execute(text('ALTER TABLE users ADD COLUMN first_interaction DATETIME DEFAULT CURRENT_TIMESTAMP'))
                    
                    # 检查并添加 bot_blocked 列
                    if 'bot_blocked' not in columns:
                        logger.info("添加 bot_blocked 列...")
                        session.execute(text('ALTER TABLE users ADD COLUMN bot_blocked BOOLEAN DEFAULT FALSE'))
                    
                    # 检查并添加 is_banned 列
                    if 'is_banned' not in columns:
                        logger.info("添加 is_banned 列...")
                        session.execute(text('ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT FALSE'))
                    
                    # 检查并添加 is_reviewer 列
                    if 'is_reviewer' not in columns:
                        logger.info("添加 is_reviewer 列...")
                        session.execute(text('ALTER TABLE users ADD COLUMN is_reviewer BOOLEAN DEFAULT FALSE'))
                
                # 检查 submissions 表
                if 'submissions' in inspector.get_table_names():
                    columns = [col['name'] for col in inspector.get_columns('submissions')]
                    
                    # 检查并添加缺失的列
                    if 'file_ids' not in columns:
                        logger.info("添加 file_ids 列...")
                        session.execute(text('ALTER TABLE submissions ADD COLUMN file_ids TEXT DEFAULT "[]"'))
                    
                    if 'cover_index' not in columns:
                        logger.info("添加 cover_index 列...")
                        session.execute(text('ALTER TABLE submissions ADD COLUMN cover_index INTEGER DEFAULT 0'))
                        
                    if 'reject_reason' not in columns:
                        logger.info("添加 reject_reason 列...")
                        session.execute(text('ALTER TABLE submissions ADD COLUMN reject_reason TEXT'))
                        
                    if 'tags' not in columns:
                        logger.info("添加 tags 列...")
                        session.execute(text('ALTER TABLE submissions ADD COLUMN tags TEXT DEFAULT "[]"'))
                        
                    if 'handled_by' not in columns:
                        logger.info("添加 handled_by 列...")
                        session.execute(text('ALTER TABLE submissions ADD COLUMN handled_by INTEGER'))
                        
                    if 'handled_at' not in columns:
                        logger.info("添加 handled_at 列...")
                        session.execute(text('ALTER TABLE submissions ADD COLUMN handled_at DATETIME'))
                    
                    if 'file_types' not in columns:
                        logger.info("添加 file_types 列...")
                        session.execute(text('ALTER TABLE submissions ADD COLUMN file_types TEXT DEFAULT "[]"'))
                
                # 检查 ban_records 表
                if 'ban_records' in inspector.get_table_names():
                    columns = [col['name'] for col in inspector.get_columns('ban_records')]
                    
                    # 检查并添加缺失的列
                    if 'unbanned_by' not in columns:
                        logger.info("添加 unbanned_by 列...")
                        session.execute(text('ALTER TABLE ban_records ADD COLUMN unbanned_by INTEGER'))
                    
                    if 'unbanned_at' not in columns:
                        logger.info("添加 unbanned_at 列...")
                        session.execute(text('ALTER TABLE ban_records ADD COLUMN unbanned_at DATETIME'))
                        
                    # 新增：检查并添加已发布消息ID相关的列
                    if 'published_message_id' not in columns:
                        logger.info("添加 published_message_id 列...")
                        session.execute(text('ALTER TABLE submissions ADD COLUMN published_message_id VARCHAR(100)'))
                        
                    if 'published_channel_message_ids' not in columns:
                        logger.info("添加 published_channel_message_ids 列...")
                        session.execute(text('ALTER TABLE submissions ADD COLUMN published_channel_message_ids TEXT DEFAULT "[]"'))
                        
                    if 'published_group_message_ids' not in columns:
                        logger.info("添加 published_group_message_ids 列...")
                        session.execute(text('ALTER TABLE submissions ADD COLUMN published_group_message_ids TEXT DEFAULT "[]"'))
                        
                    # 新增：检查并添加回访评价相关列
                    if 'feedback_sent' not in columns:
                        logger.info("添加 feedback_sent 列...")
                        session.execute(text('ALTER TABLE submissions ADD COLUMN feedback_sent BOOLEAN DEFAULT FALSE'))
                        
                    if 'feedback_sent_at' not in columns:
                        logger.info("添加 feedback_sent_at 列...")
                        session.execute(text('ALTER TABLE submissions ADD COLUMN feedback_sent_at DATETIME'))
                
                # 检查 reviewer_applications 表
                if 'reviewer_applications' in inspector.get_table_names():
                    columns = [col['name'] for col in inspector.get_columns('reviewer_applications')]
                    
                    if 'reason' not in columns:
                        logger.info("添加 reason 列...")
                        session.execute(text('ALTER TABLE reviewer_applications ADD COLUMN reason TEXT'))
                        
                session.commit()
                    
        except Exception as e:
            logger.error(f"检查/添加列失败: {e}")
    
    def _fallback_initialization(self, db_url):
        """备用初始化方法 - 确保系统可以正常运行
        
        当主初始化失败时，使用基本配置初始化数据库
        
        Args:
            db_url: 数据库连接URL
        """
        try:
            logger.info("尝试使用基本配置初始化数据库...")
            
            # 使用基本连接配置
            self.engine = create_engine(db_url)
            self.Session = sessionmaker(bind=self.engine)
            
            # 创建基本表结构
            Base.metadata.create_all(self.engine)
            
            logger.info("数据库备用初始化成功")
            
        except Exception as fallback_error:
            logger.critical(f"数据库备用初始化也失败: {fallback_error}")
            raise RuntimeError(f"无法初始化数据库，系统无法启动: {fallback_error}")
    
    def _create_ban_records_table(self):
        """创建封禁记录表"""
        try:
            inspector = inspect(self.engine)
            if 'ban_records' not in inspector.get_table_names():
                Base.metadata.tables['ban_records'].create(self.engine)
                logger.info("创建 ban_records 表")
        except Exception as e:
            logger.error(f"创建 ban_records 表失败: {e}")
    
    @contextmanager
    def session_scope(self):
        """提供一个数据库会话上下文管理器"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库会话错误: {e}")
            raise
        finally:
            try:
                session.close()
            except Exception as e:
                logger.warning(f"关闭数据库会话时出错: {e}")
    
    def get_session(self):
        """获取数据库会话"""
        return self.Session()
    
    # 用户相关操作
    def add_or_update_user(self, user):
        """添加或更新用户信息"""
        try:
            with self.session_scope() as session:
                existing_user = session.query(User).filter_by(user_id=user.id).first()
                if existing_user:
                    # 更新现有用户信息
                    existing_user.username = user.username
                    existing_user.first_name = user.first_name
                    existing_user.last_name = user.last_name
                    # 使用setattr来避免类型错误
                    setattr(existing_user, 'is_bot', getattr(user, 'is_bot', False))
                    setattr(existing_user, 'language_code', getattr(user, 'language_code', None))
                    setattr(existing_user, 'last_interaction', func.now())
                else:
                    # 添加新用户
                    new_user = User(
                        user_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        is_bot=getattr(user, 'is_bot', False),
                        language_code=getattr(user, 'language_code', None)
                    )
                    session.add(new_user)
                return True
        except Exception as e:
            logger.error(f"添加或更新用户失败: {e}")
            return False
    
    def get_user_by_id(self, user_id):
        """根据用户ID获取用户信息"""
        try:
            with self.session_scope() as session:
                return session.query(User).filter_by(user_id=user_id).first()
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None
    
    def get_all_users(self):
        """获取所有用户"""
        try:
            with self.session_scope() as session:
                return session.query(User).all()
        except Exception as e:
            logger.error(f"获取所有用户失败: {e}")
            return []
    
    def get_user_count(self):
        """获取用户总数"""
        try:
            with self.session_scope() as session:
                return session.query(User).count()
        except Exception as e:
            logger.error(f"获取用户数量失败: {e}")
            return 0
    
    def get_blocked_user_count(self):
        """获取被屏蔽用户数量"""
        try:
            with self.session_scope() as session:
                return session.query(User).filter_by(bot_blocked=True).count()
        except Exception as e:
            logger.error(f"获取被屏蔽用户数量失败: {e}")
            return 0
    
    # 投稿相关操作
    def add_submission(self, user_id, username, content_type, content, file_id=None, 
                      file_ids=None, tags=None, category='submission', anonymous=False, file_types=None):
        """添加投稿记录
        
        Args:
            user_id: 用户ID
            username: 用户名
            content_type: 内容类型(text/photo/video)
            content: 内容文本
            file_id: 媒体文件ID
            file_ids: 多媒体文件ID列表
            tags: 标签列表
            category: 分类(submission/business)
            anonymous: 是否匿名
            file_types: 文件类型列表
            
        Returns:
            int: 投稿ID，失败返回None
        """
        try:
            with self.session_scope() as session:
                if file_ids is None:
                    file_ids = []
                if file_id and file_id not in file_ids:
                    file_ids.append(file_id)
                
                if tags is None:
                    tags = []
                    
                if file_types is None:
                    file_types = []
                    
                submission = Submission(
                    user_id=user_id,
                    username=username,
                    type=content_type,
                    content=content,
                    file_id=file_id,
                    file_ids=json.dumps(file_ids),
                    file_types=json.dumps(file_types),
                    tags=json.dumps(tags),
                    category=category,
                    anonymous=anonymous,
                    status='pending'  # 确保所有投稿默认状态为pending
                )
                session.add(submission)
                session.flush()  # 获取ID但不提交
                return submission.id
        except Exception as e:
            logger.error(f"添加投稿失败: {e}")
            return None
    
    def get_submission(self, sub_id):
        """获取投稿记录
        
        Args:
            sub_id: 投稿ID
            
        Returns:
            Submission: 投稿对象，不存在返回None
        """
        try:
            with self.session_scope() as session:
                return session.query(Submission).filter_by(id=sub_id).first()
        except Exception as e:
            logger.error(f"获取投稿失败: {e}")
            return None
    
    def update_status(self, sub_id, status, handled_by=None):
        """更新投稿状态
        
        Args:
            sub_id: 投稿ID
            status: 新状态
            handled_by: 处理人ID
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            with self.session_scope() as session:
                submission = session.query(Submission).filter_by(id=sub_id).first()
                if submission:
                    submission.status = status
                    if handled_by is not None:
                        submission.handled_by = handled_by
                        setattr(submission, 'handled_at', func.now())
                    return True
                return False
        except Exception as e:
            logger.error(f"更新状态失败: {e}")
            return False
    
    def update_cover_index(self, sub_id, cover_index):
        """更新封面索引
        
        Args:
            sub_id: 投稿ID
            cover_index: 封面索引
        
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            with self.session_scope() as session:
                submission = session.query(Submission).filter_by(id=sub_id).first()
                if submission:
                    submission.cover_index = cover_index
                    return True
                return False
        except Exception as e:
            logger.error(f"更新封面索引失败: {e}")
            return False
    
    def update_reject_reason(self, sub_id, reason):
        """更新拒绝原因
        
        Args:
            sub_id: 投稿ID
            reason: 拒绝原因
        
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            with self.session_scope() as session:
                submission = session.query(Submission).filter_by(id=sub_id).first()
                if submission:
                    submission.reject_reason = reason
                    return True
                return False
        except Exception as e:
            logger.error(f"更新拒绝原因失败: {e}")
            return False
    
    def update_submission_tags(self, sub_id, tags):
        """更新投稿标签
        
        Args:
            sub_id: 投稿ID
            tags: 标签列表
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            with self.session_scope() as session:
                submission = session.query(Submission).filter_by(id=sub_id).first()
                if submission:
                    setattr(submission, 'tags', json.dumps(tags))
                    return True
                return False
        except Exception as e:
            logger.error(f"更新投稿标签失败: {e}")
            return False
    
    def get_all_tags(self):
        """获取所有使用的标签
        
        Returns:
            dict: 标签及其使用次数
        """
        try:
            with self.session_scope() as session:
                # 获取预定义标签
                predefined_tags = session.query(Tag).all()
                tag_counts = {tag.name: tag.usage_count for tag in predefined_tags}
                
                # 获取投稿中使用的标签
                submissions = session.query(Submission).filter(
                    Submission.status == 'approved'
                ).all()
                
                # 创建一个新的字典来存储计数，避免类型冲突
                count_dict = {}
                for submission in submissions:
                    try:
                        tags = json.loads(getattr(submission, 'tags', '[]')) if getattr(submission, 'tags') else []
                        for tag in tags:
                            if tag not in count_dict:
                                count_dict[tag] = 0
                            else:
                                count_dict[tag] = count_dict[tag] + 1
                    except:
                        continue
                # 合并计数字典
                for tag, count in count_dict.items():
                    if tag in tag_counts:
                        tag_counts[tag] = tag_counts[tag] + count
                    else:
                        tag_counts[tag] = count
                
                return tag_counts
        except Exception as e:
            logger.error(f"获取标签统计失败: {e}")
            return {}
    
    def add_tag(self, tag_name):
        """添加新标签
        
        Args:
            tag_name: 标签名称
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            with self.session_scope() as session:
                # 检查标签是否已存在
                existing_tag = session.query(Tag).filter_by(name=tag_name).first()
                if existing_tag:
                    return False
                    
                new_tag = Tag(name=tag_name)
                session.add(new_tag)
                return True
        except Exception as e:
            logger.error(f"添加标签失败: {e}")
            return False
    
    def get_pending_submissions(self):
        """获取待审投稿列表
        
        Returns:
            list: 待审投稿列表
        """
        try:
            with self.session_scope() as session:
                submissions = session.query(Submission).filter_by(status='pending').all()
                
                # 在会话内提取所有需要的数据，避免返回绑定到会话的对象
                result = []
                for submission in submissions:
                    # 提取所有属性值
                    sub_data = {
                        'id': getattr(submission, 'id'),
                        'user_id': getattr(submission, 'user_id'),
                        'username': getattr(submission, 'username'),
                        'type': getattr(submission, 'type'),
                        'content': getattr(submission, 'content'),
                        'file_id': getattr(submission, 'file_id'),
                        'file_ids': getattr(submission, 'file_ids'),
                        'file_types': getattr(submission, 'file_types') if hasattr(submission, 'file_types') else None,
                        'tags': getattr(submission, 'tags'),
                        'status': getattr(submission, 'status'),
                        'category': getattr(submission, 'category'),
                        'anonymous': getattr(submission, 'anonymous'),
                        'cover_index': getattr(submission, 'cover_index'),
                        'reject_reason': getattr(submission, 'reject_reason'),
                        'handled_by': getattr(submission, 'handled_by'),
                        'handled_at': getattr(submission, 'handled_at'),
                        'timestamp': getattr(submission, 'timestamp')
                    }
                    result.append(sub_data)
                
                return result
        except Exception as e:
            logger.error(f"获取待审稿件失败: {e}")
            return []
    
    def get_pending_submissions_paginated(self, limit=50, offset=0):
        """获取待审投稿列表（支持分页）
        
        Args:
            limit: 限制返回数量
            offset: 偏移量
            
        Returns:
            list: 待审投稿列表
        """
        try:
            with self.session_scope() as session:
                submissions = session.query(Submission).filter_by(status='pending').\
                    order_by(Submission.timestamp.desc()).\
                    limit(limit).offset(offset).all()
                
                # 在会话内提取所有需要的数据，避免返回绑定到会话的对象
                result = []
                for submission in submissions:
                    # 提取所有属性值
                    sub_data = {
                        'id': getattr(submission, 'id'),
                        'user_id': getattr(submission, 'user_id'),
                        'username': getattr(submission, 'username'),
                        'type': getattr(submission, 'type'),
                        'content': getattr(submission, 'content'),
                        'file_id': getattr(submission, 'file_id'),
                        'file_ids': getattr(submission, 'file_ids'),
                        'file_types': getattr(submission, 'file_types') if hasattr(submission, 'file_types') else None,
                        'tags': getattr(submission, 'tags'),
                        'status': getattr(submission, 'status'),
                        'category': getattr(submission, 'category'),
                        'anonymous': getattr(submission, 'anonymous'),
                        'cover_index': getattr(submission, 'cover_index'),
                        'reject_reason': getattr(submission, 'reject_reason'),
                        'handled_by': getattr(submission, 'handled_by'),
                        'handled_at': getattr(submission, 'handled_at'),
                        'timestamp': getattr(submission, 'timestamp')
                    }
                    result.append(sub_data)
                
                return result
        except Exception as e:
            logger.error(f"获取待审投稿失败: {e}")
            return []
    
    def get_pending_submissions_count(self):
        """获取待审投稿数量
        
        Returns:
            int: 待审投稿数量
        """
        try:
            with self.session_scope() as session:
                return session.query(Submission).filter_by(status='pending').count()
        except Exception as e:
            logger.error(f"获取待审投稿数量失败: {e}")
            return 0
    
    def get_user_submissions_paginated(self, user_id, limit=20, offset=0):
        """获取用户投稿列表（支持分页）
        
        Args:
            user_id: 用户ID
            limit: 限制返回数量
            offset: 偏移量
            
        Returns:
            list: 用户投稿列表
        """
        try:
            with self.session_scope() as session:
                submissions = session.query(Submission).filter_by(user_id=user_id).\
                    order_by(Submission.timestamp.desc()).\
                    limit(limit).offset(offset).all()
                
                # 在会话内提取所有需要的数据，避免返回绑定到会话的对象
                result = []
                for submission in submissions:
                    # 提取所有属性值
                    sub_data = {
                        'id': getattr(submission, 'id'),
                        'user_id': getattr(submission, 'user_id'),
                        'username': getattr(submission, 'username'),
                        'type': getattr(submission, 'type'),
                        'content': getattr(submission, 'content'),
                        'file_id': getattr(submission, 'file_id'),
                        'file_ids': getattr(submission, 'file_ids'),
                        'file_types': getattr(submission, 'file_types') if hasattr(submission, 'file_types') else None,
                        'tags': getattr(submission, 'tags'),
                        'status': getattr(submission, 'status'),
                        'category': getattr(submission, 'category'),
                        'anonymous': getattr(submission, 'anonymous'),
                        'cover_index': getattr(submission, 'cover_index'),
                        'reject_reason': getattr(submission, 'reject_reason'),
                        'handled_by': getattr(submission, 'handled_by'),
                        'handled_at': getattr(submission, 'handled_at'),
                        'timestamp': getattr(submission, 'timestamp')
                    }
                    result.append(sub_data)
                
                return result
        except Exception as e:
            logger.error(f"获取用户投稿失败: {e}")
            return []
    
    def get_submissions_by_status_paginated(self, status, limit=50, offset=0):
        """按状态获取投稿列表（支持分页）
        
        Args:
            status: 投稿状态
            limit: 限制返回数量
            offset: 偏移量
            
        Returns:
            list: 投稿列表
        """
        try:
            with self.session_scope() as session:
                submissions = session.query(Submission).filter_by(status=status).\
                    order_by(Submission.timestamp.desc()).\
                    limit(limit).offset(offset).all()
                
                # 在会话内提取所有需要的数据，避免返回绑定到会话的对象
                result = []
                for submission in submissions:
                    # 提取所有属性值
                    sub_data = {
                        'id': getattr(submission, 'id'),
                        'user_id': getattr(submission, 'user_id'),
                        'username': getattr(submission, 'username'),
                        'type': getattr(submission, 'type'),
                        'content': getattr(submission, 'content'),
                        'file_id': getattr(submission, 'file_id'),
                        'file_ids': getattr(submission, 'file_ids'),
                        'file_types': getattr(submission, 'file_types') if hasattr(submission, 'file_types') else None,
                        'tags': getattr(submission, 'tags'),
                        'status': getattr(submission, 'status'),
                        'category': getattr(submission, 'category'),
                        'anonymous': getattr(submission, 'anonymous'),
                        'cover_index': getattr(submission, 'cover_index'),
                        'reject_reason': getattr(submission, 'reject_reason'),
                        'handled_by': getattr(submission, 'handled_by'),
                        'handled_at': getattr(submission, 'handled_at'),
                        'timestamp': getattr(submission, 'timestamp')
                    }
                    result.append(sub_data)
                
                return result
        except Exception as e:
            logger.error(f"获取投稿列表失败: {e}")
            return []
    
    def get_business_requests(self):
        """获取商务合作请求列表
        
        Returns:
            list: 商务合作请求列表
        """
        try:
            with self.session_scope() as session:
                submissions = session.query(Submission).filter_by(
                    category='business', 
                    status='pending'
                ).all()
                
                # 在会话内提取所有需要的数据，避免返回绑定到会话的对象
                result = []
                for submission in submissions:
                    # 提取所有属性值
                    sub_data = {
                        'id': getattr(submission, 'id'),
                        'user_id': getattr(submission, 'user_id'),
                        'username': getattr(submission, 'username'),
                        'type': getattr(submission, 'type'),
                        'content': getattr(submission, 'content'),
                        'file_id': getattr(submission, 'file_id'),
                        'file_ids': getattr(submission, 'file_ids'),
                        'file_types': getattr(submission, 'file_types') if hasattr(submission, 'file_types') else None,
                        'tags': getattr(submission, 'tags'),
                        'status': getattr(submission, 'status'),
                        'category': getattr(submission, 'category'),
                        'anonymous': getattr(submission, 'anonymous'),
                        'cover_index': getattr(submission, 'cover_index'),
                        'reject_reason': getattr(submission, 'reject_reason'),
                        'handled_by': getattr(submission, 'handled_by'),
                        'handled_at': getattr(submission, 'handled_at'),
                        'timestamp': getattr(submission, 'timestamp')
                    }
                    result.append(sub_data)
                
                return result
        except Exception as e:
            logger.error(f"获取商务合作失败: {e}")
            return []
    
    def set_user_state(self, user_id, state, data=None):
        """设置用户状态
        
        Args:
            user_id: 用户ID
            state: 状态
            data: 状态数据
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        if data is None:
            data = {}
        try:
            with self.session_scope() as session:
                user_state = session.query(UserState).filter_by(user_id=user_id).first()
                if user_state:
                    user_state.state = state
                    # 正确设置Column字段的值
                    setattr(user_state, 'data', json.dumps(data, ensure_ascii=False))
                else:
                    new_state = UserState(
                        user_id=user_id,
                        state=state,
                        data=json.dumps(data, ensure_ascii=False)
                    )
                    session.add(new_state)
                # 确保提交事务
                session.commit()
                logger.info(f"[DEBUG] User state set for user {user_id}: state={state}, data={data}")
                return True
        except Exception as e:
            logger.error(f"设置用户状态失败: {e}")
            return False

    def get_user_state(self, user_id):
        """获取用户状态
        
        Args:
            user_id: 用户ID
            
        Returns:
            tuple: (状态, 数据) 或 (None, {})
        """
        try:
            with self.session_scope() as session:
                user_state = session.query(UserState).filter_by(user_id=user_id).first()
                if user_state:
                    # 正确访问Column字段的值
                    data_value = getattr(user_state, 'data')
                    if data_value:
                        try:
                            data = json.loads(str(data_value))
                        except (json.JSONDecodeError, TypeError):
                            data = {}
                    else:
                        data = {}
                    logger.info(f"[DEBUG] User state retrieved for user {user_id}: state={user_state.state}, data={data}")
                    return user_state.state, data
                logger.info(f"[DEBUG] No user state found for user {user_id}")
                return None, {}
        except Exception as e:
            logger.error(f"获取用户状态失败: {e}")
            return None, {}
    
    def get_submission_count(self):
        """获取投稿总数
        
        Returns:
            int: 投稿总数
        """
        try:
            with self.session_scope() as session:
                return session.query(Submission).count()
        except Exception as e:
            logger.error(f"获取投稿总数失败: {e}")
            return 0
    
    def get_approved_submissions_count(self):
        """获取已批准投稿数量
        
        Returns:
            int: 已批准投稿数量
        """
        try:
            with self.session_scope() as session:
                return session.query(Submission).filter_by(status='approved').count()
        except Exception as e:
            logger.error(f"获取已批准投稿数量失败: {e}")
            return 0
    
    def get_rejected_submissions_count(self):
        """获取已拒绝投稿数量
        
        Returns:
            int: 已拒绝投稿数量
        """
        try:
            with self.session_scope() as session:
                return session.query(Submission).filter_by(status='rejected').count()
        except Exception as e:
            logger.error(f"获取已拒绝投稿数量失败: {e}")
            return 0
    
    def get_database_stats(self):
        """获取数据库统计信息
        
        Returns:
            dict: 数据库统计信息
        """
        try:
            stats = {}
            
            # 获取数据库文件大小（仅适用于SQLite）
            if DB_URL.startswith('sqlite:///'):
                import os
                db_file = DB_URL.replace('sqlite:///', '')
                if os.path.exists(db_file):
                    stats['database_size_mb'] = os.path.getsize(db_file) / (1024 * 1024)
            
            # 获取各种统计信息
            stats['total_submissions'] = self.get_submission_count()
            stats['pending_submissions'] = self.get_pending_submissions_count()
            stats['rejected_submissions'] = self.get_rejected_submissions_count()
            stats['user_states'] = self.get_user_states_count()
            
            return stats
        except Exception as e:
            logger.error(f"获取数据库统计失败: {e}")
            return {}
    
    def clear_user_state(self, user_id):
        """清除用户状态
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            with self.session_scope() as session:
                session.query(UserState).filter_by(user_id=user_id).delete()
                return True
        except Exception as e:
            logger.error(f"清除用户状态失败: {e}")
            return False
    
    def clear_all_user_states(self):
        """清除所有用户状态
        
        用于系统重启时清理所有用户的交互状态
        
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            with self.session_scope() as session:
                deleted_count = session.query(UserState).delete()
                logger.info(f"已清理 {deleted_count} 个用户状态")
                return True
        except Exception as e:
            logger.error(f"清除所有用户状态失败: {e}")
            return False
    
    def cleanup_old_data(self, days=30):
        """清理旧数据"""
        try:
            with self.session_scope() as session:
                # 计算截止时间
                cutoff = get_beijing_now() - timedelta(days=days)
                # 删除旧的用户状态数据
                deleted_count = session.query(UserState).filter(
                    UserState.last_interaction < cutoff
                ).delete()
                session.commit()
                return deleted_count
        except Exception as e:
            logger.error(f"清理旧用户状态数据失败: {e}")
            return 0

    def cleanup_inactive_user_states(self, minutes=120):
        """清理非活跃用户状态"""
        try:
            with self.session_scope() as session:
                # 计算截止时间
                cutoff = get_beijing_now() - timedelta(minutes=minutes)
                # 删除非活跃用户状态
                deleted_count = session.query(UserState).filter(
                    UserState.last_interaction < cutoff
                ).delete()
                session.commit()
                logger.info(f"清理了 {deleted_count} 个超过 {minutes} 分钟无交互的用户状态")
                return deleted_count
        except Exception as e:
            logger.error(f"清理非活跃用户状态失败: {e}")
            return 0
    
    # 审核员申请相关方法
    def add_reviewer_application(self, user_id, username, reason=None):
        """添加审核员申请
        
        Args:
            user_id: 用户ID
            username: 用户名
            reason: 申请理由
            
        Returns:
            int: 申请ID，失败返回None
        """
        try:
            with self.session_scope() as session:
                # 检查是否已有待处理的申请
                existing = session.query(ReviewerApplication).filter_by(
                    user_id=user_id, 
                    status='pending'
                ).first()
                
                if existing:
                    return existing.id
                    
                application = ReviewerApplication(
                    user_id=user_id,
                    username=username,
                    reason=reason)
                session.add(application)
                session.flush()  # 获取ID但不提交
                
                # 同时更新User表中的is_reviewer字段为False（表示正在申请中）
                user = session.query(User).filter_by(user_id=user_id).first()
                if user:
                    setattr(user, 'is_reviewer', False)
                
                return application.id
        except Exception as e:
            logger.error(f"添加审核员申请失败: {e}")
            return None
    
    def get_pending_applications(self):
        """获取待处理的审核员申请列表
        
        Returns:
            list: 待处理申请列表
        """
        try:
            with self.session_scope() as session:
                return session.query(ReviewerApplication).filter_by(status='pending').all()
        except Exception as e:
            logger.error(f"获取待处理申请失败: {e}")
            return []
    
    def handle_application(self, application_id: int, admin_id: int, action: str, reason: str = ""): 
        """处理审核员申请"""
        try:
            with self.session_scope() as session:
                application = session.query(ReviewerApplication).filter_by(id=application_id).first()
                if application:
                    setattr(application, 'status', action)
                    setattr(application, 'handled_by', admin_id)
                    setattr(application, 'handled_at', get_beijing_now())
                    setattr(application, 'reason', reason or '')
                    
                    # 如果申请被批准，更新用户表中的is_reviewer字段
                    if action == 'approved':
                        user = session.query(User).filter_by(user_id=application.user_id).first()
                        if user:
                            setattr(user, 'is_reviewer', True)
                    # 如果申请被拒绝，更新用户表中的is_reviewer字段为False
                    elif action in ['rejected', 'pending']:
                        user = session.query(User).filter_by(user_id=application.user_id).first()
                        if user:
                            setattr(user, 'is_reviewer', False)
                    
                    session.commit()
                    return True
        except Exception as e:
            logger.error(f"处理审核员申请失败: {e}")
        return False
    
    def get_application_by_user(self, user_id):
        """获取用户的申请
        
        Args:
            user_id: 用户ID
            
        Returns:
            ReviewerApplication: 申请对象，不存在返回None
        """
        try:
            with self.session_scope() as session:
                # 获取用户的最新申请记录
                return session.query(ReviewerApplication).filter_by(
                    user_id=user_id
                ).order_by(ReviewerApplication.timestamp.desc()).first()
        except Exception as e:
            logger.error(f"获取用户申请失败: {e}")
            return None
    
    def get_application_by_id(self, app_id):
        """根据ID获取申请记录
        
        Args:
            app_id: 申请ID
            
        Returns:
            ReviewerApplication: 申请对象，不存在返回None
        """
        try:
            with self.session_scope() as session:
                return session.query(ReviewerApplication).filter_by(id=app_id).first()
        except Exception as e:
            logger.error(f"获取申请失败: {e}")
            return None
    
    def update_application_invite_link(self, app_id, invite_link):
        """更新申请的邀请链接
        
        Args:
            app_id: 申请ID
            invite_link: 邀请链接
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            with self.session_scope() as session:
                application = session.query(ReviewerApplication).filter_by(id=app_id).first()
                if application:
                    application.invite_link = invite_link
                    return True
                return False
        except Exception as e:
            logger.error(f"更新邀请链接失败: {e}")
            return False
    
    def update_reviewer_permissions(self, user_id, permissions):
        """更新审核员权限设置
        
        Args:
            user_id: 审核员用户ID
            permissions: 权限设置字典
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            with self.session_scope() as session:
                reviewer = session.query(ReviewerApplication).filter_by(
                    user_id=user_id,
                    status='approved'
                ).first()
                
                if reviewer:
                    setattr(reviewer, 'permissions', json.dumps(permissions))
                    return True
                return False
        except Exception as e:
            logger.error(f"更新审核员权限失败: {e}")
            return False
    
    def get_reviewer_permissions(self, user_id):
        """获取审核员权限设置
        
        Args:
            user_id: 审核员用户ID
            
        Returns:
            dict: 权限设置字典
        """
        try:
            with self.session_scope() as session:
                reviewer = session.query(ReviewerApplication).filter_by(
                    user_id=user_id,
                    status='approved'
                ).first()
                
                if reviewer and getattr(reviewer, 'permissions'):
                    try:
                        return json.loads(getattr(reviewer, 'permissions'))
                    except json.JSONDecodeError:
                        return {}
                return {}
        except Exception as e:
            logger.error(f"获取审核员权限失败: {e}")
            return {}
    
    def get_user_states_count(self):
        """获取用户状态数量"""
        try:
            with self.session_scope() as session:
                return session.query(UserState).count()
        except Exception as e:
            logger.error(f"获取用户状态数量失败: {e}")
            return 0
    
    def get_user_submission_stats(self, user_id):
        """获取用户投稿统计信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            dict: 包含用户投稿统计信息的字典
        """
        try:
            with self.session_scope() as session:
                # 获取用户的各种投稿统计
                total = session.query(Submission).filter_by(user_id=user_id).count()
                approved = session.query(Submission).filter_by(user_id=user_id, status='approved').count()
                rejected = session.query(Submission).filter_by(user_id=user_id, status='rejected').count()
                pending = session.query(Submission).filter_by(user_id=user_id, status='pending').count()
                
                # 计算通过率
                approval_rate = (approved / total * 100) if total > 0 else 0
                
                return {
                    'total': total,
                    'approved': approved,
                    'rejected': rejected,
                    'pending': pending,
                    'approval_rate': approval_rate
                }
        except Exception as e:
            logger.error(f"获取用户投稿统计失败: {e}")
            # 返回默认值
            return {
                'total': 0,
                'approved': 0,
                'rejected': 0,
                'pending': 0,
                'approval_rate': 0
            }

    # 封禁相关操作
    def check_ban_status(self, user_id):
        """检查用户封禁状态"""
        try:
            with self.session_scope() as session:
                # 检查是否有永久封禁记录
                permanent_ban = session.query(BanRecord).filter_by(
                    user_id=user_id, 
                    ban_type='permanent',
                    unbanned_at=None
                ).first()
                
                if permanent_ban:
                    return {
                        "is_banned": True,
                        "type": "permanent",
                        "ban_start": permanent_ban.ban_start,
                        "reason": permanent_ban.reason
                    }
                
                # 检查临时封禁记录
                temp_ban = session.query(BanRecord).filter(
                    BanRecord.user_id == user_id,
                    BanRecord.ban_type == 'temporary',
                    BanRecord.unbanned_at == None,
                    BanRecord.ban_end > func.now()
                ).first()
                
                if temp_ban:
                    return {
                        "is_banned": True,
                        "type": "temporary",
                        "ban_start": temp_ban.ban_start,
                        "ban_end": temp_ban.ban_end,
                        "reason": temp_ban.reason
                    }
                
                return {"is_banned": False}
        except Exception as e:
            logger.error(f"检查封禁状态失败: {e}")
            return {"is_banned": False}

    def update_user_bot_blocked(self, user_id, is_blocked):
        """更新用户bot_blocked状态
        
        Args:
            user_id: 用户ID
            is_blocked: 是否屏蔽(True=屏蔽/删除, False=正常)
            
        Returns:
            bool: 操作是否成功
        """
        try:
            with self.session_scope() as session:
                user = session.query(User).filter_by(user_id=user_id).first()
                if user:
                    setattr(user, 'bot_blocked', is_blocked)
                    return True
                return False
        except Exception as e:
            logger.error(f"更新用户bot_blocked状态失败: {e}")
            return False

    def ban_user(self, user_id: int, ban_type: str, reason: str = "", banned_by: int = 0):
        """封禁用户"""
        try:
            with self.session_scope() as session:
                # 计算封禁结束时间
                ban_end = get_beijing_now() + timedelta(days=7) if ban_type == 'temporary' else None
                
                # 创建封禁记录
                ban_record = BanRecord(
                    user_id=user_id,
                    ban_type=ban_type,
                    reason=reason,
                    banned_by=banned_by,
                    ban_end=ban_end
                )
                session.add(ban_record)
                session.commit()
                
                # 更新用户状态
                user = session.query(User).filter_by(user_id=user_id).first()
                if user:
                    setattr(user, 'is_banned', True)
                    setattr(user, 'ban_reason', reason or '')
                    session.commit()
                
                return ban_record.id
        except Exception as e:
            logger.error(f"封禁用户失败: {e}")
            return None

    def unban_user(self, user_id: int, unbanned_by: int = 0):
        """解封用户"""
        try:
            with self.session_scope() as session:
                # 更新所有未结束的封禁记录
                session.query(BanRecord).filter_by(
                    user_id=user_id,
                    ban_end=None
                ).update({
                    "ban_end": get_beijing_now(),
                    "unbanned_by": unbanned_by,
                    "unbanned_at": get_beijing_now()
                })
                session.commit()
                
                # 更新用户状态
                user = session.query(User).filter_by(user_id=user_id).first()
                if user:
                    setattr(user, 'is_banned', False)
                    setattr(user, 'ban_reason', '')
                    session.commit()
                
                # 记录解封事件
                unban_event = {
                    "user_id": user_id,
                    "unbanned_by": unbanned_by,
                    "unbanned_at": get_beijing_now()
                }
                
                return unban_event
        except Exception as e:
            logger.error(f"解封用户失败: {e}")
            return None

    def get_system_config(self):
        """获取系统配置"""
        try:
            with self.session_scope() as session:
                config = session.query(SystemConfig).first()
                if config:
                    # 处理可能为None的情况
                    channel_ids = getattr(config, 'channel_ids', '') or ''
                    group_ids = getattr(config, 'group_ids', '') or ''
                    disabled_channels = getattr(config, 'disabled_channels', '') or ''
                    disabled_groups = getattr(config, 'disabled_groups', '') or ''
                    
                    return {
                        'channel_ids': channel_ids.split(',') if channel_ids else [],
                        'group_ids': group_ids.split(',') if group_ids else [],
                        'disabled_channels': disabled_channels.split(',') if disabled_channels else [],
                        'disabled_groups': disabled_groups.split(',') if disabled_groups else []
                    }
                return None
        except Exception as e:
            logger.error(f"获取系统配置失败: {e}")
            return None

    def update_system_config(self, channel_ids=None, group_ids=None, disabled_channels=None, disabled_groups=None):
        """更新系统配置"""
        try:
            with self.session_scope() as session:
                config = session.query(SystemConfig).first()
                if not config:
                    config = SystemConfig()
                    session.add(config)
                
                if channel_ids is not None:
                    # 使用setattr来避免类型错误
                    setattr(config, 'channel_ids', ','.join(channel_ids) if channel_ids else '')
                
                if group_ids is not None:
                    # 使用setattr来避免类型错误
                    setattr(config, 'group_ids', ','.join(group_ids) if group_ids else '')
                
                if disabled_channels is not None:
                    # 使用setattr来避免类型错误
                    setattr(config, 'disabled_channels', ','.join(disabled_channels) if disabled_channels else '')
                
                if disabled_groups is not None:
                    # 使用setattr来避免类型错误
                    setattr(config, 'disabled_groups', ','.join(disabled_groups) if disabled_groups else '')
                
                session.commit()
                return True
        except Exception as e:
            logger.error(f"更新系统配置失败: {e}")
            return False

    def disable_channel(self, channel_id):
        """禁用频道"""
        try:
            with self.session_scope() as session:
                config = session.query(SystemConfig).first()
                if not config:
                    config = SystemConfig()
                    session.add(config)
                
                # 获取当前禁用的频道
                disabled_channels = getattr(config, 'disabled_channels', '') or ''
                disabled_channels_list = disabled_channels.split(',') if disabled_channels else []
                
                # 添加要禁用的频道（如果尚未禁用）
                if channel_id not in disabled_channels_list:
                    disabled_channels_list.append(channel_id)
                    setattr(config, 'disabled_channels', ','.join(disabled_channels_list))
                
                session.commit()
                return True
        except Exception as e:
            logger.error(f"禁用频道失败: {e}")
            return False

    def disable_group(self, group_id):
        """禁用群组"""
        try:
            with self.session_scope() as session:
                config = session.query(SystemConfig).first()
                if not config:
                    config = SystemConfig()
                    session.add(config)
                
                # 获取当前禁用的群组
                disabled_groups = getattr(config, 'disabled_groups', '') or ''
                disabled_groups_list = disabled_groups.split(',') if disabled_groups else []
                
                # 添加要禁用的群组（如果尚未禁用）
                if group_id not in disabled_groups_list:
                    disabled_groups_list.append(group_id)
                    setattr(config, 'disabled_groups', ','.join(disabled_groups_list))
                
                session.commit()
                return True
        except Exception as e:
            logger.error(f"禁用群组失败: {e}")
            return False

    def enable_channel(self, channel_id):
        """启用频道"""
        try:
            with self.session_scope() as session:
                config = session.query(SystemConfig).first()
                if not config:
                    return True  # 如果没有配置，说明频道是启用的
                
                # 获取当前禁用的频道
                disabled_channels = getattr(config, 'disabled_channels', '') or ''
                disabled_channels_list = disabled_channels.split(',') if disabled_channels else []
                
                # 移除要启用的频道
                if channel_id in disabled_channels_list:
                    disabled_channels_list.remove(channel_id)
                    setattr(config, 'disabled_channels', ','.join(disabled_channels_list))
                
                session.commit()
                return True
        except Exception as e:
            logger.error(f"启用频道失败: {e}")
            return False

    def enable_group(self, group_id):
        """启用群组"""
        try:
            with self.session_scope() as session:
                config = session.query(SystemConfig).first()
                if not config:
                    return True  # 如果没有配置，说明群组是启用的
                
                # 获取当前禁用的群组
                disabled_groups = getattr(config, 'disabled_groups', '') or ''
                disabled_groups_list = disabled_groups.split(',') if disabled_groups else []
                
                # 移除要启用的群组
                if group_id in disabled_groups_list:
                    disabled_groups_list.remove(group_id)
                    setattr(config, 'disabled_groups', ','.join(disabled_groups_list))
                
                session.commit()
                return True
        except Exception as e:
            logger.error(f"启用群组失败: {e}")
            return False

    def upgrade_database(self):
        """升级数据库结构"""
        try:
            # 创建所有表（包括新添加的表和字段）
            Base.metadata.create_all(self.engine)
            logger.info("数据库结构已更新")
            return True
        except Exception as e:
            logger.error(f"数据库升级失败: {e}")
            return False

    def auto_ban_blocked_users(self, since):
        """自动封禁屏蔽机器人超过指定时间的用户
        
        Args:
            since: 时间点，此时间之前屏蔽的用户将被封禁
            
        Returns:
            int: 被封禁的用户数量
        """
        try:
            with self.session_scope() as session:
                # 查询屏蔽机器人且屏蔽时间早于指定时间的用户
                users_to_ban = session.query(User).filter(
                    User.bot_blocked.is_(True),
                    User.last_interaction < since
                ).all()
                
                banned_count = 0
                for user in users_to_ban:
                    # 检查用户是否已经被封禁
                    if not getattr(user, 'is_banned', False):
                        setattr(user, 'is_banned', True)
                        banned_count += 1
                        logger.info(f"自动封禁用户 {user.user_id}，该用户屏蔽机器人已超过3天")
                
                session.commit()
                return banned_count
        except Exception as e:
            logger.error(f"自动封禁屏蔽用户失败: {e}")
            return 0

# 全局数据库管理实例
db = DatabaseManager()