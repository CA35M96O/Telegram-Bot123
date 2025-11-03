# Telegram 投稿机器人系统

## 🚀 项目简介

这是一个功能完善的 Telegram 投稿管理机器人系统，支持用户投稿、管理员审核、自动发布等全流程管理。系统经过全面优化，具备高性能、高可靠性和良好的用户体验。

> ⚠️ **重要提示**：本项目需要配合存储机器人一起使用才能发挥完整功能。请确保同时部署并配置存储机器人以保证系统的正常运行。

### ✨ 核心特性

- **🎯 多类型投稿支持**: 文本、图片、视频、混合媒体投稿
- **👥 用户管理**: 成员资格验证、用户状态跟踪、匿名投稿
- **🔍 智能审核**: 多级审核流程、批量处理、审核员权限管理
- **📊 数据统计**: 实时统计、历史数据分析、可视化图表
- **🏷️ 标签系统**: 灵活的标签管理、自动分类、统计分析
- **🔔 推送通知**: PushPlus 集成、实时消息推送
- **📱 客服支持**: 在线客服系统、联系方式管理
- **📈 回访评价**: 投稿发布后自动回访评价
- **⚙️ 系统配置**: 动态频道/群组管理、配置持久化

### 🆕 最新版本特性 (v2.3.3)

- **安全性增强**: 实现SSL证书验证控制，生产环境启用完整验证，开发环境可跳过验证
- **网络连接优化**: 添加动态DNS解析机制和故障转移功能，提高连接稳定性
- **推送可靠性提升**: 实现推送失败重试队列和推送状态跟踪机制
- **缓存系统增强**: 添加缓存持久化机制和缓存预热功能
- **安全防护加强**: 更新恶意模式检测规则，添加机器学习异常检测功能
- **代码健壮性提升**: 修复多个None对象访问问题，增强异常处理机制

### 🆕 版本特性 (v2.3.2)

- **用户权限系统增强**: 审核员现在可以查看用户列表和进行封禁操作
- **用户体验改进**: 在个人中心显示用户身份信息
- **封禁系统优化**: 实现基于次数的封禁策略（3次临时封禁转为永久封禁）
- **界面优化**: 审核员面板移除仅管理员可访问的功能
- **系统稳定性提升**: 修复了"Message is not modified"等错误
- **频道/群组管理增强**: 支持动态添加、删除和禁用频道/群组，正确区分默认配置和自定义配置
- 改进频道/群组详情查看功能
- 修复默认频道/群组识别问题

### 🆕 版本特性 (v2.1)

- **投稿回访评价**: 投稿发布24小时后自动回访评价
- **浏览量统计**: 估算投稿在频道中的浏览量
- **等级评价**: 根据浏览占比给出S/A/B/C等级评价
- **私聊反馈**: 将评价结果私聊发送给投稿人

### 🆕 版本特性 (v2.0)

- **混合媒体投稿**: 同时支持图片和视频的混合投稿
- **智能媒体分组**: 自动将不同类型媒体分组发布
- **增强的错误处理**: 多层错误处理机制，确保系统稳定性
- **性能优化**: 数据库连接池、缓存机制、批量处理
- **安全性提升**: 环境变量配置、安全的回调处理

## 📋 目录结构

```
电报机器人/
├── main.py                    # 主程序入口
├── config.py                  # 配置文件
├── config_env.py             # 环境变量配置
├── database.py               # 数据库模型和操作
├── keyboards.py              # 键盘布局定义
├── requirements.txt          # 依赖包列表
├── .env.example             # 环境变量模板
├── .env.template            # 环境变量模板
├── .gitignore              # Git忽略文件
├── handlers/               # 消息处理器
│   ├── __init__.py
│   ├── admin.py           # 管理员功能（已模块化，保留兼容性）
│   ├── admin_temp.py      # 临时管理员功能
│   ├── submission.py      # 投稿处理
│   ├── start.py           # 启动和主菜单
│   ├── help.py            # 帮助系统
│   ├── privacy.py         # 隐私政策
│   ├── business.py        # 业务逻辑
│   ├── membership.py      # 成员资格验证
│   ├── reviewer_application.py  # 审核员申请
│   ├── user_profile.py    # 用户档案
│   ├── user_experience.py # 用户体验
│   ├── review.py          # 投稿审核
│   ├── history.py         # 历史投稿管理
│   ├── statistics.py      # 数据统计
│   ├── user_management.py # 用户管理
│   ├── backup.py          # 数据备份
│   ├── cleanup.py         # 数据清理
│   ├── bug_commands.py    # Bug命令处理
│   └── error.py           # 错误处理
├── utils/                 # 工具模块
│   ├── __init__.py
│   ├── helpers.py         # 辅助函数
│   ├── security.py        # 安全模块
│   ├── monitoring.py      # 监控系统
│   ├── cache.py           # 缓存管理
│   ├── cached_db.py       # 缓存数据库
│   ├── push_queue.py      # 推送队列
│   ├── wxpusher.py        # WxPusher推送
│   ├── pushplus.py        # PushPlus推送
│   ├── logging_utils.py   # 日志工具
│   ├── time_utils.py      # 时间工具
│   ├── server_status.py   # 服务器状态
│   ├── backup.py          # 备份工具
│   ├── cleanup.py         # 清理工具
│   ├── db_optimization.py      # 数据库优化
│   ├── cache_optimization.py   # 缓存优化
│   ├── memory_optimizer.py     # 内存优化
│   ├── security_optimization.py # 安全优化
│   ├── monitoring_tuning.py    # 监控调优
│   ├── monitoring_init.py      # 监控初始化
│   ├── bug_logger.py           # Bug日志记录
│   ├── bug_analyzer.py         # Bug分析
│   ├── log_analyzer.py         # 日志分析
│   └── user_experience.py      # 用户体验工具
├── jobs/                  # 定时任务
│   ├── __init__.py
│   ├── cleanup.py         # 清理任务
│   ├── dns_monitor.py     # DNS监控
│   ├── advanced_scheduler.py # 高级调度器
│   ├── submission_feedback.py # 投稿回访评价
│   ├── status_report.py   # 状态报告
│   └── bug_analysis.py    # Bug分析
├── logs/                  # 日志文件
│   ├── bot.log           # 机器人主日志
│   ├── bot_errors.log    # 错误日志
│   ├── admin_operations.log     # 管理操作日志
│   ├── user_activities.log      # 用户活动日志
│   ├── bugs_database.log        # 数据库Bug日志
│   ├── bugs_media.log           # 媒体Bug日志
│   ├── bugs_permission.log      # 权限Bug日志
│   ├── bugs_resource.log        # 资源Bug日志
│   ├── bugs_external.log        # 外部服务Bug日志
│   ├── bugs_input.log           # 输入Bug日志
│   ├── bugs_scheduler.log       # 定时任务Bug日志
│   ├── bugs_unknown.log         # 未知Bug日志
│   └── debug.log                # 调试日志
└── backups/              # 数据备份目录
```

## ⚙️ 环境配置

### 1. 系统要求

- Python 3.8 或更高版本
- 内存: 最少 512MB，推荐 1GB+
- 磁盘空间: 最少 1GB 可用空间
- 网络: 稳定的互联网连接

### 2. 安装依赖

```
# 克隆项目（如果从仓库获取）
git clone <repository_url>
cd 电报机器人

# 安装Python依赖
pip install -r requirements.txt
```

**依赖更新日志**:
- 2025-09-07: 更新了多个依赖包到最新稳定版本

### 3. 环境变量配置

复制环境变量模板：
```bash
cp .env.example .env
```

编辑 `.env` 文件，填入您的配置：

```
# 机器人Token（必填）
BOT_TOKEN=your_bot_token_here

# 管理员ID列表（逗号分隔）
ADMIN_IDS=123456789,987654321

# 管理群组ID
MANAGEMENT_GROUP_ID=-1001234567890

# 频道ID列表（逗号分隔）
CHANNEL_IDS=@your_channel1,@your_channel2

# 群组ID列表（逗号分隔）
GROUP_IDS=-1001234567890,-1009876543210

# 数据库配置
DB_URL=sqlite:///submissions.db

# 成员资格验证配置
VERIFY_GROUP_IDS=-1001234567890,-1009876543210
VERIFY_CHANNEL_IDS=@your_channel1,@your_channel2
ENFORCE_GROUP_MEMBERSHIP=true
ENFORCE_CHANNEL_MEMBERSHIP=false

# 统一的解锁链接 - 群组和频道使用同一个链接
UNLOCK_LINK=https://t.me/your_group

# 客服联系配置
CUSTOMER_SUPPORT_LINK=https://t.me/your_support
CUSTOMER_SUPPORT_USERNAME=@your_support
CUSTOMER_SUPPORT_NAME=客服中心
CUSTOMER_SUPPORT_HOURS=09:00-22:00
CUSTOMER_SUPPORT_TIMEZONE=北京时间

# 系统配置
LOG_LEVEL=INFO
SERVER_NAME=默认服务器
SHOW_DETAILED_STATS=true

# PushPlus通知（可选）
PUSHPLUS_TOKEN=your_pushplus_token
PUSHPLUS_TOPIC=your_topic

# 数据库性能配置
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600

# 分页配置
DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=100

# 缓存配置
CACHE_TIMEOUT=300
MAX_CACHE_SIZE=1000

# 通知优化配置
NOTIFICATION_BATCH_SIZE=10
NOTIFICATION_DELAY=0.1
MAX_RETRY_ATTEMPTS=3

# 清理任务配置
CLEANUP_RETENTION_DAYS=30
CLEANUP_BATCH_SIZE=100

# 系统监控配置
MONITOR_INTERVAL=60
MEMORY_WARNING_THRESHOLD=80
CPU_WARNING_THRESHOLD=80

# 异步处理配置
ENABLE_ASYNC_PROCESSING=false
MAX_CONCURRENT_TASKS=5

# 日志配置
LOG_FILE_MAX_SIZE=10485760
LOG_BACKUP_COUNT=5
ENABLE_FILE_LOGGING=true
```

### 4. 数据库初始化

首次运行时，数据库表会自动创建。如需手动初始化：

```python
from database import init_db
init_db()
```

## 🚀 快速开始

### 1. 创建机器人

1. 在 Telegram 中找到 [@BotFather](https://t.me/botfather)
2. 发送 `/newbot` 创建新机器人
3. 设置机器人名称和用户名
4. 获取机器人Token并配置到 `.env` 文件

### 2. 配置权限

机器人需要以下权限：
- 发送消息
- 发送媒体文件
- 使用内联键盘
- 访问群组成员列表（如启用成员验证）

### 3. 启动机器人

```bash
python main.py
```

### 4. 初始化管理员

首次启动后：
1. 将您的用户ID添加到 `ADMIN_IDS` 环境变量
2. 重启机器人
3. 向机器人发送 `/start` 即可看到管理员面板

## 📖 功能说明

### 用户功能

1. **投稿系统**
   - 支持文本、图片、视频、混合媒体投稿
   - 匿名投稿选项
   - 标签选择和自定义
   - 投稿进度查询

2. **用户体验**
   - 直观的菜单导航
   - 详细的操作指引
   - 快速帮助和FAQ
   - 个人投稿历史

3. **回访评价**
   - 投稿发布24小时后自动回访
   - 浏览量统计和等级评价(S/A/B/C)
   - 私聊发送评价结果

### 管理员功能

1. **投稿审核**
   - 分页浏览待审投稿
   - 多媒体内容预览
   - 快速审核操作
   - 批量处理支持

2. **数据统计**
   - 实时数据面板
   - 历史趋势分析
   - 用户活跃度统计

3. **系统管理**
   - 用户管理（封禁/解封）
   - 标签管理
   - 广播消息
   - 数据备份和清理
   - 动态频道/群组配置增强

4. **任务调度**
   - 定时清理任务
   - 回访评价任务
   - 系统维护任务

### 审核员功能

1. **投稿审核**
   - 审核用户投稿
   - 查看投稿详情和多媒体内容
   - 添加标签

2. **用户管理**
   - 查看用户列表
   - 封禁/解封用户

## 🔄 工作流程

### 投稿流程
1. 用户发送 `/start` 启动机器人
2. 选择"我要投稿"
3. 选择投稿类型（文本/图片/视频/混合媒体）
4. 输入内容并确认
5. 等待管理员审核
6. 审核通过后自动发布到频道
7. 发布24小时后收到回访评价

### 审核流程
1. 管理员收到新投稿通知
2. 查看投稿内容
3. 选择通过/拒绝/联系用户
4. 如通过则自动发布到频道
5. 系统记录审核信息

### 回访评价流程
1. 系统定时检查已发布24小时以上的投稿
2. 估算投稿浏览量和频道总人数
3. 计算浏览占比并给出等级评价
4. 私聊发送评价结果给投稿人

## ⚙️ 配置说明

### 核心配置项
- `BOT_TOKEN`: Telegram Bot Token
- `ADMIN_IDS`: 管理员用户ID列表
- `CHANNEL_IDS`: 频道ID列表
- `GROUP_IDS`: 群组ID列表
- `VERIFY_GROUP_IDS`: 需要验证的群组ID列表
- `VERIFY_CHANNEL_IDS`: 需要验证的频道ID列表
- `UNLOCK_LINK`: 统一的解锁链接，群组和频道使用同一个链接

### 性能配置项
- `DB_POOL_SIZE`: 数据库连接池大小
- `DEFAULT_PAGE_SIZE`: 默认分页大小
- `CACHE_TIMEOUT`: 缓存超时时间

## 📈 回访评价等级标准

系统根据投稿浏览占比给出等级评价：
- **S级**: 浏览占比 ≥ 10%
- **A级**: 浏览占比 ≥ 5%
- **B级**: 浏览占比 ≥ 2%
- **C级**: 浏览占比 < 2%

## 🔧 维护和日志

### 日志管理
- 系统日志: `logs/bot.log`
- 错误日志: `logs/bot_errors.log`
- 用户活动日志: `logs/user_activities.log`
- 管理员操作日志: `logs/admin_operations.log`

### 定时任务
- 数据清理: 定期清理过期数据
- 回访评价: 自动发送投稿回访评价
- DNS监控: 监控网络连接状态

## 🆕 更新日志

### v2.3.3 (2025-10-31)
- **安全性增强**: 实现SSL证书验证控制，生产环境启用完整验证，开发环境可跳过验证
- **网络连接优化**: 添加动态DNS解析机制和故障转移功能，提高连接稳定性
- **推送可靠性提升**: 实现推送失败重试队列和推送状态跟踪机制
- **缓存系统增强**: 添加缓存持久化机制和缓存预热功能
- **安全防护加强**: 更新恶意模式检测规则，添加机器学习异常检测功能
- **代码健壮性提升**: 修复多个None对象访问问题，增强异常处理机制

### v2.3.2 (2025-10-21)
- 系统配置增强：支持动态添加、删除和禁用频道/群组
- 修复频道/群组删除功能问题
- 优化频道/群组显示逻辑，正确区分默认配置和自定义配置
- 改进频道/群组详情查看功能
- 修复默认频道/群组识别问题

### v2.3.1 (2025-10-21)
- 系统配置增强：支持动态添加、删除和禁用频道/群组
- 修复频道/群组删除功能问题
- 优化频道/群组显示逻辑，正确区分默认配置和自定义配置

### v2.3.0 (2025-10-18)
- 用户权限系统增强：审核员现在可以查看用户列表和进行封禁操作
- 用户体验改进：在个人中心显示用户身份信息
- 封禁系统优化：实现基于次数的封禁策略（3次临时封禁转为永久封禁）
- 界面优化：审核员面板移除仅管理员可访问的功能
- 系统稳定性提升：修复了"Message is not modified"等错误

### v2.2.0 (2025-10-17)
- 系统架构优化：对 handlers/admin.py 进行模块化重构，将其拆分为多个专门的功能模块
- 新增模块：review.py（审核功能）、history.py（历史投稿管理）、statistics.py（数据统计）、tag_management.py（标签管理）、user_management.py（用户管理）、system_management.py（系统管理）、backup.py（备份功能）、cleanup.py（清理功能）
- 代码可维护性提升：通过模块化降低了各功能之间的耦合度，便于后续维护和扩展

### v2.1.1 (2025-09-12)
- 系统优化：移除了冗余的监控仪表板、任务管理和缓存管理模块
- 简化系统架构：保留核心功能，提高系统稳定性和可维护性

### v2.1.0 (2025-09-11)
- 新增投稿回访评价功能
- 自动统计投稿浏览量并给出等级评价
- 私聊发送回访评价结果给投稿人

### v2.0.0 (2025-08-31)
- 新增混合媒体投稿功能
- 性能优化和数据库连接池
- 增强的错误处理机制

## 📞 技术支持

如有任何问题，请联系技术支持。

---

## 📄 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

---

*最后更新时间：2025-10-31*