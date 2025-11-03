# keyboards.py
"""
键盘布局生成模块 - Telegram 内联键盘组件库

本模块负责生成机器人使用的所有内联键盘布局，包括：
- 主菜单和导航键盘布局
- 投稿相关操作键盘（文本、媒体、混合）
- 管理员和审核员专用功能键盘
- 商务合作申请表单键盘
- 分页导航和确认操作键盘

设计原则：
- 用户友好的界面布局和交互流程
- 响应式按钮排列和自适应宽度
- 一致的视觉风格和图标使用
- 国际化支持（中文界面）
- 功能分组和层次化导航
- 状态敏感的动态按钮显示

键盘类型：
1. 静态键盘 - 固定布局，如主菜单
2. 动态键盘 - 根据状态变化，如审核面板
3. 表单键盘 - 交互式表单，如商务合作
4. 分页键盘 - 支持翻页导航的列表

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram import InlineKeyboardMarkup as InlineKeyboardMarkupType
from config import UNLOCK_LINK

# 从环境变量获取群组和频道URL，如果不存在则使用默认值
import os
from config import UNLOCK_LINK
GROUP_URL = os.getenv("GROUP_URL", UNLOCK_LINK)
CHANNEL_URL = os.getenv("CHANNEL_URL", UNLOCK_LINK)

async def main_menu(user_id=None, is_admin=False, context=None) -> "InlineKeyboardMarkup":
    """
    生成主菜单键盘布局
    
    主菜单包含所有用户都可以访问的基本功能，
    并根据用户角色动态添加管理员专用功能。
    
    功能按钮：
    - 投稿菜单：进入各种投稿类型选择
    - 商务合作：商务合作申请表单
    - 个人中心：查看个人信息和投稿历史
    - 加入管理群：仅对不在管理群中的审核员显示
    - 管理面板：仅管理员可见
    
    Args:
        user_id (int): 用户ID
        is_admin (bool): 是否为管理员或审核员
        context: Telegram上下文对象
        
    Returns:
        InlineKeyboardMarkup: 主菜单键盘布局对象
    """
    # 构建基础菜单选项 - 所有用户都可以访问的功能
    keyboard_list = [
        [InlineKeyboardButton("📤 我要投稿", callback_data="submit_menu")],
        [InlineKeyboardButton("🤝 商务合作", callback_data="business_menu")],
        [InlineKeyboardButton("👤 个人中心", callback_data="user_profile")]
    ]
    
    # 只对不在管理群中的审核员显示"加入管理群"按钮
    show_apply_reviewer = False
    if is_admin and user_id and context:
        try:
            from config import MANAGEMENT_GROUP_ID
            chat_member = await context.bot.get_chat_member(MANAGEMENT_GROUP_ID, user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                show_apply_reviewer = True
        except Exception:
            # 如果检查失败，默认不显示按钮
            show_apply_reviewer = False
    
    if is_admin and show_apply_reviewer:
        keyboard_list.append([InlineKeyboardButton("👑 加入管理群", callback_data="apply_reviewer")])
    
    # 管理员或审核员专用功能 - 根据权限动态添加
    if is_admin:  # 管理员和审核员都显示管理面板入口
        keyboard_list.append([InlineKeyboardButton("⚙️ 管理面板", callback_data="admin_panel")])
        
    return InlineKeyboardMarkup(keyboard_list)  # type: ignore

def membership_check_menu(missing_group="group") -> "InlineKeyboardMarkup":
    """成员资格检查菜单
    
    Args:
        missing_group: 缺少加入的群组类型 (group/channel)
        
    Returns:
        InlineKeyboardMarkup: 成员资格检查键盘布局
    """
    if missing_group == "channel":
        join_button = InlineKeyboardButton("📢 加入频道", url=CHANNEL_URL)
    else:
        join_button = InlineKeyboardButton("👥 加入群组", url=GROUP_URL)
    
    keyboard_list = [
        [join_button],
        [InlineKeyboardButton("✅ 我已加入", callback_data="check_membership")],
        [InlineKeyboardButton("❌ 取消", callback_data="cancel_membership")]
    ]
    
    return InlineKeyboardMarkup(keyboard_list)  # type: ignore

def reviewer_panel_menu() -> "InlineKeyboardMarkup":
    """
    生成审核员面板菜单键盘
    
    审核员专用的简化操作面板，包含最常用的审核功能。
    相比管理员面板，去除了高级管理功能，仅保留审核相关操作。
    
    功能按钮：
    - 待审稿件：查看待审核的投稿
    - 历史投稿：查看已审核的投稿历史
    - 返回主菜单：返回主界面
    
    Returns:
        InlineKeyboardMarkup: 审核员面板键盘布局对象
    """
    keyboard_list = [
        [InlineKeyboardButton("📬 待审稿件", callback_data="admin_pending")],
        [InlineKeyboardButton("📋 历史投稿", callback_data="history_submissions")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard_list)  # type: ignore

def submission_type_menu(anonymous=False) -> "InlineKeyboardMarkup":
    """
    生成投稿类型选择菜单键盘
    
    用户点击"我要投稿"后显示的投稿类型选择界面。
    支持两种主要投稿类型：文字投稿和媒体投稿。
    
    功能按钮：
    - 文字投稿：纯文本内容投稿
    - 媒体投稿：包含图片、视频等媒体内容的投稿
    - 当前匿名状态显示
    - 匿名投稿切换按钮
    - 返回主菜单：取消投稿操作
    
    Args:
        anonymous (bool): 是否匿名投稿
        
    Returns:
        InlineKeyboardMarkup: 投稿类型键盘布局对象
    """
    keyboard_list = [
        [InlineKeyboardButton("📝 文字投稿", callback_data="submit_text")],
        [InlineKeyboardButton("🎥 媒体投稿", callback_data="submit_mixed_media")],
        [InlineKeyboardButton(f"当前状态: {'🎭 匿名投稿' if anonymous else '👤 实名投稿'}", callback_data="noop")],
        [
            InlineKeyboardButton(
                f"{'👤 切换为匿名投稿' if not anonymous else '👥 切换为实名投稿'}", 
                callback_data=f"toggle_submit_anonymous_{'true' if not anonymous else 'false'}"
            )
        ],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard_list)  # type: ignore

def media_type_menu() -> "InlineKeyboardMarkup":
    """媒体类型选择菜单
    
    Returns:
        InlineKeyboardMarkup: 媒体类型键盘布局
    """
    # 根据最新要求，此菜单不再使用
    # 保留函数以防代码中其他地方引用
    keyboard_list = [
        [InlineKeyboardButton("🔙 返回投稿菜单", callback_data="submit_menu")]
    ]
    return InlineKeyboardMarkup(keyboard_list)  # type: ignore

def admin_panel_menu() -> "InlineKeyboardMarkup":
    """管理员面板菜单
    
    Returns:
        InlineKeyboardMarkup: 管理员面板键盘布局
    """
    keyboard_list = [
        [
            InlineKeyboardButton("📬 待审稿件", callback_data="admin_pending"),
            InlineKeyboardButton("📋 历史投稿", callback_data="history_submissions")
        ],
        [
            InlineKeyboardButton("👥 用户列表", callback_data="user_list"),  # 仅管理员可见
            InlineKeyboardButton("📊 投稿统计", callback_data="submission_stats")
        ],
        [
            InlineKeyboardButton("📈 数据统计", callback_data="data_stats"),
            InlineKeyboardButton("🖥 服务器状态", callback_data="server_status")
        ],
        [
            InlineKeyboardButton("👥 审核员管理", callback_data="reviewer_management")
        ],
        [
            InlineKeyboardButton("📢 全员通知", callback_data="broadcast_message")
        ],
        [InlineKeyboardButton("🔄 重启机器人", callback_data="restart_bot")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard_list)  # type: ignore

def admin_panel_menu_for_reviewer() -> "InlineKeyboardMarkup":
    """审核员使用的管理员面板菜单（不包含用户列表、服务器状态和标签管理功能）
    
    Returns:
        InlineKeyboardMarkup: 审核员专用的管理员面板键盘布局
    """
    keyboard_list = [
        [
            InlineKeyboardButton("📬 待审稿件", callback_data="admin_pending"),
            InlineKeyboardButton("📋 历史投稿", callback_data="history_submissions")
        ],
        [
            InlineKeyboardButton("📊 投稿统计", callback_data="submission_stats"),
            InlineKeyboardButton("📈 数据统计", callback_data="data_stats")
        ],
        [
            InlineKeyboardButton("👥 用户列表", callback_data="user_list")
        ],
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard_list)  # type: ignore

def reviewer_management_menu() -> "InlineKeyboardMarkup":
    """审核员管理菜单
    
    Returns:
        InlineKeyboardMarkup: 审核员管理键盘布局
    """
    keyboard_list = [
        [
            InlineKeyboardButton("📋 审核员列表", callback_data="reviewer_list"),
            InlineKeyboardButton("📥 添加审核员", callback_data="add_reviewer")
        ],
        [
            InlineKeyboardButton("📤 删除审核员", callback_data="remove_reviewer"),
            InlineKeyboardButton("⚙️ 权限设置", callback_data="reviewer_permissions")
        ],
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard_list)  # type: ignore

def reviewer_applications_menu(applications, current_index=0):
    """审核员申请菜单
    
    Args:
        applications: 申请列表
        current_index: 当前页索引
        
    Returns:
        InlineKeyboardMarkup: 审核员申请键盘布局
    """
    buttons = []
    
    # 添加分页按钮
    if len(applications) > 1:
        page_buttons = []
        if current_index > 0:
            page_buttons.append(InlineKeyboardButton("⬅️ 上一个", callback_data=f"application_{current_index-1}"))
        
        page_buttons.append(InlineKeyboardButton(f"{current_index+1}/{len(applications)}", callback_data="noop"))
        
        if current_index < len(applications) - 1:
            page_buttons.append(InlineKeyboardButton("下一个 ➡️", callback_data=f"application_{current_index+1}"))
        
        buttons.append(page_buttons)
    
    # 添加操作按钮
    if applications:
        app = applications[current_index]
        buttons.append([
            InlineKeyboardButton("✅ 批准", callback_data=f"approve_application_{app.id}"),
            InlineKeyboardButton("❌ 拒绝", callback_data=f"reject_application_{app.id}")
        ])
    
    buttons.append([InlineKeyboardButton("🔙 返回", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(buttons)  # type: ignore

def server_status_menu():
    """服务器状态菜单
    
    Returns:
        InlineKeyboardMarkup: 服务器状态键盘布局
    """
    keyboard = [
        [InlineKeyboardButton("🔄 刷新状态", callback_data="server_status")],
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def reviewer_panel_menu_custom(permissions=None):
    """自定义审核员面板菜单
    
    Args:
        permissions: 审核员权限设置
        
    Returns:
        InlineKeyboardMarkup: 自定义审核员面板键盘布局
    """
    # 默认权限（向后兼容）
    if permissions is None:
        permissions = {
            'can_review': True,
            'can_history': True,
            'can_stats': True,
            'can_users': True
            # 注意：审核员不应有审核员管理权限
        }
    
    keyboard = []
    
    # 第一行：投稿相关功能
    row1 = []
    if permissions.get('can_review', True):
        row1.append(InlineKeyboardButton("📬 待审稿件", callback_data="admin_pending"))
    
    if permissions.get('can_history', True):
        row1.append(InlineKeyboardButton("📋 历史投稿", callback_data="history_submissions"))
    
    if row1:
        keyboard.append(row1)
    
    # 第二行：统计相关功能
    row2 = []
    if permissions.get('can_stats', True):
        row2.append(InlineKeyboardButton("📊 投稿统计", callback_data="submission_stats"))
        row2.append(InlineKeyboardButton("📈 数据统计", callback_data="data_stats"))
    
    if row2:
        keyboard.append(row2)
    
    # 第三行：管理相关功能（仅用户列表）
    row3 = []
    if permissions.get('can_users', True):
        row3.append(InlineKeyboardButton("👥 用户列表", callback_data="user_list"))
    
    if row3:
        keyboard.append(row3)
    
    # 返回按钮
    keyboard.append([InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)



def reviewer_permissions_menu(user_id, permissions=None):
    """审核员权限设置菜单
    
    Args:
        user_id: 审核员用户ID
        permissions: 当前权限设置
        
    Returns:
        InlineKeyboardMarkup: 审核员权限设置键盘布局
    """
    # 默认权限设置
    if permissions is None:
        permissions = {
            'can_review': True,
            'can_history': True,
            'can_stats': True,
            'can_users': True
            # 注意：审核员不应有审核员管理权限
        }
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅' if permissions.get('can_review', True) else '❌'} 审核稿件",
                callback_data=f"toggle_perm_{user_id}_can_review"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if permissions.get('can_history', True) else '❌'} 历史投稿",
                callback_data=f"toggle_perm_{user_id}_can_history"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if permissions.get('can_stats', True) else '❌'} 数据统计",
                callback_data=f"toggle_perm_{user_id}_can_stats"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if permissions.get('can_users', True) else '❌'} 用户列表",
                callback_data=f"toggle_perm_{user_id}_can_users"
            )
        ],
        [InlineKeyboardButton("💾 保存设置", callback_data=f"save_perm_{user_id}")],
        [InlineKeyboardButton("🔙 返回审核员列表", callback_data="reviewer_list")]
    ]
    
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def back_button(callback_data="main_menu") -> "InlineKeyboardMarkup":
    """返回按钮
    
    Args:
        callback_data: 返回时的回调数据
        
    Returns:
        InlineKeyboardMarkup: 包含返回按钮的键盘布局
    """
    keyboard = [[InlineKeyboardButton("🔙 返回", callback_data=callback_data)]]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def confirm_submission_menu(submission_type, anonymous=False) -> "InlineKeyboardMarkup":
    """确认投稿菜单
    
    Args:
        submission_type: 投稿类型 (text/photo/video/media)
        anonymous: 是否匿名投稿
        
    Returns:
        InlineKeyboardMarkup: 确认投稿键盘布局
    """
    keyboard_list = [
        [
            InlineKeyboardButton("✅ 确认投稿", callback_data=f"confirm_{submission_type}"),
            InlineKeyboardButton("✏️ 重新编辑", callback_data=f"edit_{submission_type}")
        ],
        [
            InlineKeyboardButton(
                f"{'👤 匿名投稿' if not anonymous else '👥 实名投稿'}", 
                callback_data=f"toggle_anonymous_{submission_type}"
            )
        ],
        [InlineKeyboardButton("🏠 返回首页", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard_list)  # type: ignore

def business_form_menu(form_data) -> "InlineKeyboardMarkup":
    """商务合作表单菜单
    
    Args:
        form_data: 表单数据
        
    Returns:
        InlineKeyboardMarkup: 商务合作表单键盘布局
    """
    keyboard = [
        [InlineKeyboardButton(
            f"🏢 公司/个人名称: {'[已填写]' if form_data.get('name') else '[未填写]'}", 
            callback_data="business_name"
        )],
        [InlineKeyboardButton(
            f"📞 联系方式: {'[已填写]' if form_data.get('contact') else '[未填写]'}", 
            callback_data="business_contact"
        )],
        [InlineKeyboardButton(
            f"💡 合作描述: {'[已填写]' if form_data.get('description') else '[未填写]'}", 
            callback_data="business_desc"
        )],
        [InlineKeyboardButton("📤 提交申请", callback_data="business_submit")],
        [InlineKeyboardButton("🏠 返回首页", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def review_panel_menu(sub_id, username="", anonymous=False, submission_data=None):
    """审核面板菜单
    
    Args:
        sub_id: 投稿ID
        username: 用户名
        anonymous: 是否匿名
        submission_data: 投稿数据，用于判断是否需要添加查看媒体按钮
        
    Returns:
        InlineKeyboardMarkup: 审核面板键盘布局
    """
    display_name = "匿名用户" if anonymous else f"@{username}"
    
    # 基本按钮
    keyboard = [
        [
            InlineKeyboardButton("✅ 通过", callback_data=f"approve_{sub_id}"),
            InlineKeyboardButton("❌ 拒绝", callback_data=f"reject_{sub_id}")
        ]
    ]
    
    # 如果是媒体投稿，添加查看媒体按钮
    if submission_data and submission_data.get('type') in ["photo", "video", "media"]:
        file_ids = submission_data.get('file_ids', [])
        file_types = submission_data.get('file_types', [])
        
        if file_ids:
            if len(file_ids) > 1:
                # 多文件投稿
                # 检查是否为混合媒体投稿
                is_mixed_media = False
                if file_types and isinstance(file_types, list):
                    has_photos = 'photo' in file_types
                    has_videos = 'video' in file_types
                    is_mixed_media = has_photos and has_videos
                
                if is_mixed_media:
                    # 混合媒体投稿，添加查看图片和视频的按钮
                    keyboard.append([
                        InlineKeyboardButton("🖼️ 查看图片", callback_data=f"view_extra_photos_{sub_id}"),
                        InlineKeyboardButton("🎬 查看视频", callback_data=f"view_extra_videos_{sub_id}")
                    ])
                else:
                    # 单一类型多文件投稿
                    # 对于media类型，需要根据file_types判断媒体类型
                    if submission_data['type'] == "media" and file_types:
                        media_type = "图片" if file_types[0] == "photo" else "视频"
                        callback_data = "view_extra_photos" if file_types[0] == "photo" else "view_extra_videos"
                    else:
                        media_type = "图片" if submission_data['type'] == "photo" else "视频"
                        callback_data = "view_extra_photos" if submission_data['type'] == "photo" else "view_extra_videos"
                    keyboard.append([
                        InlineKeyboardButton(f"📄 查看所有{media_type}", callback_data=f"{callback_data}_{sub_id}")
                    ])
            else:
                # 单文件投稿
                media_type = "图片" if submission_data['type'] == "photo" else "视频"
                callback_data = "view_extra_photos" if submission_data['type'] == "photo" else "view_extra_videos"
                keyboard.append([
                    InlineKeyboardButton(f"🖼️ 查看{media_type}", callback_data=f"{callback_data}_{sub_id}")
                ])
    
    # 添加联系用户和复制ID按钮
    keyboard.append([
        InlineKeyboardButton("💬 联系用户", callback_data=f"contact_{sub_id}"),
        InlineKeyboardButton("🆔 复制ID", callback_data=f"copy_user_id_{sub_id}")
    ])
    
    # 添加用户信息和返回按钮
    keyboard.append([InlineKeyboardButton(f"👤 用户: {display_name}", callback_data="noop")])
    keyboard.append([InlineKeyboardButton("🔙 返回", callback_data="admin_pending")])
    
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def history_review_panel_menu(sub_id, username="", anonymous=False, submission_data=None):
    """历史审核面板菜单
    
    Args:
        sub_id: 投稿ID
        username: 用户名
        anonymous: 是否匿名
        submission_data: 投稿数据，用于判断是否需要添加查看媒体按钮
        
    Returns:
        InlineKeyboardMarkup: 历史审核面板键盘布局
    """
    display_name = "匿名用户" if anonymous else f"@{username}"
    
    # 基本按钮
    keyboard = [
        [InlineKeyboardButton("🗑️ 删除已发布", callback_data=f"delete_submission_{sub_id}")],
        [InlineKeyboardButton("🔄 重新发布", callback_data=f"republish_submission_{sub_id}")]
    ]
    
    # 如果是媒体投稿，添加查看媒体按钮
    if submission_data and submission_data.get('type') in ["photo", "video", "media"]:
        file_ids = submission_data.get('file_ids', [])
        file_types = submission_data.get('file_types', [])
        
        if file_ids and len(file_ids) > 0:
            if len(file_ids) > 1:
                # 多文件投稿
                # 检查是否为混合媒体投稿
                is_mixed_media = False
                if file_types and isinstance(file_types, list):
                    has_photos = 'photo' in file_types
                    has_videos = 'video' in file_types
                    is_mixed_media = has_photos and has_videos
                
                if is_mixed_media:
                    # 混合媒体投稿，添加查看图片和视频的按钮
                    keyboard.append([
                        InlineKeyboardButton("🖼️ 查看图片", callback_data=f"history_view_photos_{sub_id}"),
                        InlineKeyboardButton("🎬 查看视频", callback_data=f"history_view_videos_{sub_id}")
                    ])
                else:
                    # 单一类型多文件投稿
                    # 对于media类型，需要根据file_types判断媒体类型
                    if submission_data['type'] == "media" and file_types:
                        media_type = "图片" if file_types[0] == "photo" else "视频"
                        callback_data = "history_view_photos" if file_types[0] == "photo" else "history_view_videos"
                    else:
                        media_type = "图片" if submission_data['type'] == "photo" else "视频"
                        callback_data = "history_view_photos" if submission_data['type'] == "photo" else "history_view_videos"
                    keyboard.append([
                        InlineKeyboardButton(f"📄 查看所有{media_type}", callback_data=f"{callback_data}_{sub_id}")
                    ])
            else:
                # 单文件投稿
                media_type = "图片" if submission_data['type'] == "photo" else "视频"
                callback_data = "history_view_photos" if submission_data['type'] == "photo" else "history_view_videos"
                keyboard.append([
                    InlineKeyboardButton(f"🖼️ 查看{media_type}", callback_data=f"{callback_data}_{sub_id}")
                ])
    
    # 添加用户信息和返回按钮
    user_id = submission_data.get('user_id', 0) if submission_data else 0
    keyboard.append([InlineKeyboardButton(f"👤 用户: {display_name}", callback_data=f"contact_user_{user_id}")])
    keyboard.append([InlineKeyboardButton("🔙 返回", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)

def mixed_media_control_menu(submission_id, media_count=0) -> "InlineKeyboardMarkup":
    """混合媒体控制菜单
    
    Args:
        submission_id: 投稿ID
        media_count: 当前媒体数量
        
    Returns:
        InlineKeyboardMarkup: 混合媒体控制键盘布局
    """
    keyboard_list = [
        [
            InlineKeyboardButton("➕ 添加图片", callback_data="add_photo_to_mixed"),
            InlineKeyboardButton("➕ 添加视频", callback_data="add_video_to_mixed")
        ]
    ]
    
    # 始终显示完成按钮，即使没有媒体文件
    keyboard_list.append([
        InlineKeyboardButton("✅ 完成添加", callback_data="finish_mixed_media")
    ])
    
    keyboard_list.append([
        InlineKeyboardButton("🔙 取消", callback_data="main_menu")
    ])
    
    return InlineKeyboardMarkup(keyboard_list)  # type: ignore

def business_menu():
    """商务合作菜单
    
    Returns:
        InlineKeyboardMarkup: 商务合作键盘布局
    """
    keyboard = [
        [InlineKeyboardButton("🏢 公司名称", callback_data="business_name")],
        [InlineKeyboardButton("📞 联系方式", callback_data="business_contact")],
        [InlineKeyboardButton("📋 合作描述", callback_data="business_desc")],
        [InlineKeyboardButton("📤 提交申请", callback_data="business_submit")],
        [InlineKeyboardButton("🏠 返回首页", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def reviewer_application_menu():
    """审核员申请菜单
    
    Returns:
        InlineKeyboardMarkup: 审核员申请键盘布局
    """
    keyboard = [
        [InlineKeyboardButton("📝 填写申请理由", callback_data="apply_reviewer")],
        [InlineKeyboardButton("🏠 返回首页", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def application_review_menu(app_id):
    """申请审核菜单
    
    Args:
        app_id: 申请ID
        
    Returns:
        InlineKeyboardMarkup: 申请审核键盘布局
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ 批准", callback_data=f"approve_application_{app_id}"),
            InlineKeyboardButton("❌ 拒绝", callback_data=f"reject_application_{app_id}")
        ],
        [InlineKeyboardButton("🔗 生成邀请链接", callback_data=f"generate_invite_{app_id}")],
        [InlineKeyboardButton("🔙 返回", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def broadcast_confirmation_menu():
    """全员通知确认菜单
    
    Returns:
        InlineKeyboardMarkup: 全员通知确认键盘布局
    """
    keyboard = [
        [InlineKeyboardButton("✅ 确认发送", callback_data="confirm_broadcast")],
        [InlineKeyboardButton("❌ 取消", callback_data="cancel_broadcast")]
    ]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def user_profile_menu():
    """个人中心菜单"""
    keyboard = [
        [InlineKeyboardButton("📊 我的统计", callback_data="my_stats")],
        [InlineKeyboardButton("🔔 微信推送设置", callback_data="wxpusher_settings")],
        [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def wxpusher_settings_menu(wxpusher_uid=None):
    """WxPusher推送设置菜单
    
    Args:
        wxpusher_uid: 当前设置的UID
        
    Returns:
        InlineKeyboardMarkup: WxPusher设置键盘布局
    """
    keyboard = [
        [InlineKeyboardButton("✏️ 修改/设置UID", callback_data="set_wxpusher_uid")],
    ]
    
    # 如果已经设置了UID，则添加测试按钮
    if wxpusher_uid:
        keyboard.append([InlineKeyboardButton("🧪 测试推送功能", callback_data="test_wxpusher")])
    
    keyboard.append([InlineKeyboardButton("🔙 返回个人中心", callback_data="user_profile")])
    
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def user_list_type_menu():
    """用户列表类型选择菜单
    
    Returns:
        InlineKeyboardMarkup: 用户列表类型选择键盘布局
    """
    keyboard = [
        [InlineKeyboardButton("✅ 正常用户列表", callback_data="normal_user_list")],
        [InlineKeyboardButton("🚫 屏蔽用户列表", callback_data="blocked_user_list")],
        [InlineKeyboardButton("🔒 封禁用户列表", callback_data="banned_user_list")],
        [InlineKeyboardButton("👥 全部用户列表", callback_data="all_user_list")],
        [InlineKeyboardButton("🆔 直接封禁/解封用户", callback_data="direct_ban_user")],
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def user_list_menu(users, current_page=0, total_pages=1, list_type="all"):
    """用户列表菜单
    
    Args:
        users: 用户列表
        current_page: 当前页码
        total_pages: 总页数
        list_type: 列表类型 (all/normal/blocked/banned)
        
    Returns:
        InlineKeyboardMarkup: 用户列表键盘布局
    """
    buttons = []
    
    # 添加用户按钮（每页最多10个用户）
    start_idx = current_page * 10
    end_idx = min(start_idx + 10, len(users))
    
    for user in users[start_idx:end_idx]:
        # 显示用户信息和状态
        is_banned = getattr(user, 'is_banned', False)
        is_blocked = getattr(user, 'bot_blocked', False)
        
        # 根据列表类型显示不同的图标
        if list_type == "banned":
            status_icon = "🔒"
        elif list_type == "blocked":
            status_icon = "🚫"
        elif is_banned:
            status_icon = "🔒"
        elif is_blocked:
            status_icon = "🚫"
        else:
            status_icon = "✅"
            
        username = getattr(user, 'username', None)
        display_name = f"@{username}" if username else f"ID: {getattr(user, 'user_id', 'Unknown')}"
        
        # 根据列表类型决定是否显示操作按钮
        if list_type in ["normal", "banned"]:
            # 正常用户和封禁用户列表不显示任何按钮
            pass
        else:
            # 屏蔽用户列表和全部用户列表不显示任何按钮
            pass
    
    # 添加分页按钮
    if total_pages > 1:
        page_buttons = []
        if current_page > 0:
            page_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"user_list_page_{current_page-1}_{list_type}"))
        
        page_buttons.append(InlineKeyboardButton(f"{current_page+1}/{total_pages}", callback_data="noop"))
        
        if current_page < total_pages - 1:
            page_buttons.append(InlineKeyboardButton("➡️", callback_data=f"user_list_page_{current_page+1}_{list_type}"))
        
        buttons.append(page_buttons)
    
    # 添加返回按钮
    buttons.append([InlineKeyboardButton("🔙 返回用户列表类型", callback_data="user_list_type")])
    
    return InlineKeyboardMarkup(buttons)  # type: ignore

def reviewer_list_menu(reviewers, current_page=0, total_pages=1):
    """审核员列表菜单
    
    Args:
        reviewers: 审核员列表
        current_page: 当前页码
        total_pages: 总页数
        
    Returns:
        InlineKeyboardMarkup: 审核员列表键盘布局
    """
    buttons = []
    
    # 添加审核员按钮（每页最多10个审核员）
    start_idx = current_page * 10
    end_idx = min(start_idx + 10, len(reviewers))
    
    for reviewer in reviewers[start_idx:end_idx]:
        username = getattr(reviewer, 'username', None)
        display_name = f"@{username}" if username else f"ID: {getattr(reviewer, 'user_id', 'Unknown')}"
        # 修复审核员列表按钮显示问题
        buttons.append([
            InlineKeyboardButton(
                f"👤 {display_name}", 
                callback_data=f"view_user_{getattr(reviewer, 'user_id', 0)}"
            ),
            InlineKeyboardButton(
                "⚙️ 权限", 
                callback_data=f"set_perm_{getattr(reviewer, 'user_id', 0)}"
            )
        ])
    
    # 添加分页按钮
    if total_pages > 1:
        page_buttons = []
        if current_page > 0:
            page_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"reviewer_list_page_{current_page-1}"))
        
        page_buttons.append(InlineKeyboardButton(f"{current_page+1}/{total_pages}", callback_data="noop"))
        
        if current_page < total_pages - 1:
            page_buttons.append(InlineKeyboardButton("➡️", callback_data=f"reviewer_list_page_{current_page+1}"))
        
        buttons.append(page_buttons)
    
    # 添加返回按钮
    buttons.append([InlineKeyboardButton("🔙 返回审核员管理", callback_data="reviewer_management")])
    
    return InlineKeyboardMarkup(buttons)  # type: ignore

def ban_user_menu(user_id, is_banned=False):
    """封禁用户菜单
    
    Args:
        user_id: 用户ID
        is_banned: 是否已被封禁
        
    Returns:
        InlineKeyboardMarkup: 封禁用户键盘布局
    """
    keyboard = [
        [InlineKeyboardButton(
            f"{'🔓 解封用户' if is_banned else '🔒 封禁用户'}", 
            callback_data=f"{'unban' if is_banned else 'ban'}_user_{user_id}"
        )],
        [InlineKeyboardButton("🔙 返回用户列表", callback_data="user_list")]
    ]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def restart_bot_confirmation_menu():
    """机器人重启确认菜单
    
    Returns:
        InlineKeyboardMarkup: 机器人重启确认键盘布局
    """
    keyboard = [
        [InlineKeyboardButton("✅ 确认重启", callback_data="confirm_restart_bot")],
        [InlineKeyboardButton("❌ 取消", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def database_backup_menu():
    """数据备份菜单
    
    Returns:
        InlineKeyboardMarkup: 数据备份键盘布局
    """
    keyboard = [
        [InlineKeyboardButton("💾 完整备份", callback_data="backup_full")],
        [InlineKeyboardButton("📄 数据库备份", callback_data="backup_database")],
        [InlineKeyboardButton("⚙️ 配置备份", callback_data="backup_config")],
        [InlineKeyboardButton("📅 日志备份", callback_data="backup_logs")],
        [InlineKeyboardButton("📈 备份状态", callback_data="backup_status")],
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def database_cleanup_menu():
    """数据清理菜单
    
    Returns:
        InlineKeyboardMarkup: 数据清理键盘布局
    """
    keyboard = [
        [InlineKeyboardButton("🧹 旧数据清理", callback_data="cleanup_old_data")],
        [InlineKeyboardButton("🗑️ 用户状态清理", callback_data="cleanup_user_states")],
        [InlineKeyboardButton("📅 日志清理", callback_data="cleanup_logs")],
        [InlineKeyboardButton("📊 数据库优化", callback_data="optimize_database")],
        [InlineKeyboardButton("🧽 垃圾收集", callback_data="garbage_collection")],
        [InlineKeyboardButton("📈 清理状态", callback_data="cleanup_status")],
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def cleanup_confirmation_menu(cleanup_type):
    """清理确认菜单
    
    Args:
        cleanup_type: 清理类型
        
    Returns:
        InlineKeyboardMarkup: 清理确认键盘布局
    """
    keyboard = [
        [InlineKeyboardButton("✅ 确认清理", callback_data=f"confirm_cleanup_{cleanup_type}")],
        [InlineKeyboardButton("❌ 取消", callback_data="database_cleanup")]
    ]
    return InlineKeyboardMarkup(keyboard)  # type: ignore

def backup_confirmation_menu(backup_type):
    """备份确认菜单
    
    Args:
        backup_type: 备份类型
        
    Returns:
        InlineKeyboardMarkup: 备份确认键盘布局
    """
    keyboard = [
        [InlineKeyboardButton("✅ 确认备份", callback_data=f"confirm_backup_{backup_type}")],
        [InlineKeyboardButton("❌ 取消", callback_data="database_backup")]
    ]
    return InlineKeyboardMarkup(keyboard)