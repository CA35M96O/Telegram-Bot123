# utils/helpers.py
"""
辅助函数模块 - 统一媒体投稿系统支持

本模块包含各种工具函数和辅助函数，主要功能包括：

核心功能：
1. 成员资格检查 - 验证用户是否加入指定群组和频道
2. 管理员通知 - 向所有管理员和审核员发送新投稿通知
3. 投稿发布 - 将通过审核的投稿发布到频道和群组
4. 分离式媒体组发布 - 自动将混合媒体按类型分组发布
5. 投稿展示 - 在管理界面中展示投稿详情

新增特性（v2.0）：
- 支持混合媒体投稿的智能分组发布
- 自动媒体类型检测和分类
- 优化的频道和群组发布流程
- 增强的错误处理和日志记录
"""

import logging
import json
import time
import asyncio
from telegram import InputMediaPhoto, InputMediaVideo, InlineKeyboardButton, InlineKeyboardMarkup
from config import CHANNEL_IDS, GROUP_IDS, ADMIN_IDS, MANAGEMENT_GROUP_ID, VERIFY_GROUP_IDS, VERIFY_CHANNEL_IDS, ENFORCE_GROUP_MEMBERSHIP, ENFORCE_CHANNEL_MEMBERSHIP
from keyboards import review_panel_menu, history_review_panel_menu

# 安全的回调查询处理函数
def safe_answer_callback_query(query, text="", show_alert=False):
    """
    安全地回答回调查询，处理超时问题
    
    Args:
        query: Telegram CallbackQuery 对象
        text: 回答文本
        show_alert: 是否显示警告
        
    Returns:
        bool: 是否成功回答
    """
    try:
        query.answer(text=text, show_alert=show_alert)
        return True
    except Exception as answer_error:
        error_msg = str(answer_error)
        if "Query is too old" in error_msg or "query id is invalid" in error_msg:
            logger.debug(f"回调查询已超时或无效： {text}")
        else:
            logger.warning(f"回答回调查询失败: {answer_error}")
        return False

logger = logging.getLogger(__name__)

async def check_membership(update, context, user_id):
    """
    检查用户是否已加入指定的群组和频道
    
    这个函数用于验证用户是否具有使用bot功能的权限。
    系统要求用户必须同时加入指定的验证群组和验证频道。
    
    检查流程：
    1. 检查用户在验证群组中的成员资格（支持多个群组）
    2. 检查用户在验证频道中的订阅状态（支持多个频道）
    3. 返回检查结果和需要加入的位置
    
    Args:
        update: Telegram 更新对象
        context: Telegram 上下文对象
        user_id (int): 要检查的用户ID
        
    Returns:
        tuple: (is_member: bool, where: str)
            - is_member: 是否已加入所有必需的地方
            - where: 需要加入的地方 ('group', 'channel', 'both', 'error')
    """
    try:
        group_check_failed = False
        channel_check_failed = False
        
        # 检查群组成员资格（只在启用时检查）- 支持多个群组
        if ENFORCE_GROUP_MEMBERSHIP:
            try:
                # 检查每个群组的成员资格
                for group_id in VERIFY_GROUP_IDS:
                    try:
                        group_member = await context.bot.get_chat_member(chat_id=group_id, user_id=user_id)
                        if group_member.status in ['left', 'kicked']:
                            group_check_failed = True
                            break  # 只要有一个群组未加入，就标记为失败
                    except Exception as group_error:
                        logger.warning(f"检查群组 {group_id} 成员资格失败: {group_error}")
                        # 如果是Chat not found错误，可能是配置问题，但不阻止用户使用
                        if "Chat not found" in str(group_error):
                            logger.error(f"群组ID配置可能有误: {group_id}")
                            # 继续检查其他群组
                        else:
                            group_check_failed = True
                            break  # 其他错误直接标记为失败
            except Exception as e:
                logger.error(f"群组成员资格检查出现异常: {e}")
                group_check_failed = True
        else:
            logger.debug("群组成员资格检查已禁用")
        
        # 检查频道订阅状态（只在启用时检查）- 支持多个频道
        if ENFORCE_CHANNEL_MEMBERSHIP and VERIFY_CHANNEL_IDS:
            try:
                # 检查每个频道的订阅状态
                for channel_id in VERIFY_CHANNEL_IDS:
                    try:
                        channel_member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                        if channel_member.status in ['left', 'kicked']:
                            channel_check_failed = True
                            break  # 只要有一个频道未加入，就标记为失败
                    except Exception as channel_error:
                        error_msg = str(channel_error)
                        logger.warning(f"检查频道 {channel_id} 订阅状态失败: {channel_error}")
                        # 如果是频道成员列表不可访问，这通常意味着频道设置了隐私保护
                        if "Member list is inaccessible" in error_msg:
                            # 频道隐私设置导致无法检查，跳过这个频道检查
                            logger.info(f"频道 {channel_id} 成员列表不可访问，跳过频道检查")
                            # 继续检查其他频道
                        elif "Chat not found" in error_msg:
                            logger.error(f"频道ID配置可能有误: {channel_id}")
                            # 继续检查其他频道
                        else:
                            channel_check_failed = True
                            break  # 其他错误直接标记为失败
            except Exception as e:
                logger.error(f"频道成员资格检查出现异常: {e}")
                channel_check_failed = True
        else:
            logger.debug("频道成员资格检查已禁用或未配置频道")
        
        # 确定返回结果
        if group_check_failed and channel_check_failed:
            return False, "both"
        elif group_check_failed:
            return False, "group"
        elif channel_check_failed:
            return False, "channel"
        else:
            return True, "both"
            
    except Exception as e:
        logger.error(f"检查成员资格出现未知错误: {e}")
        # 出现严重错误时，为了不阻止用户使用，默认返回已加入
        logger.warning("由于检查失败，允许用户继续使用")
        return True, "both"

async def notify_admins(context, submission_id):
    """通知所有管理员和审核员有新投稿
    
    Args:
        context: Telegram context 对象
        submission_id: 投稿ID
    """
    try:
        from database import db
        with db.session_scope() as session:
            from database import Submission, User, ReviewerApplication
            submission = session.query(Submission).filter_by(id=submission_id).first()
            if not submission:
                logger.error(f"通知管理员: 投稿 {submission_id} 不存在")
                return
            
            # 获取所有管理员和审核员
            from config import ADMIN_IDS
            
            # 收集需要通知的用户ID和他们的推送偏好
            recipient_data = []
            
            # 添加管理员
            for admin_id in ADMIN_IDS:
                user = session.query(User).filter_by(user_id=admin_id).first()
                if user:
                    recipient_data.append({
                        'user_id': admin_id,
                        'wxpusher_uid': getattr(user, 'wxpusher_uid', None)
                    })
            
            # 添加审核员（排除已经是管理员的审核员）
            # 查询已批准的审核员申请
            reviewer_applications = session.query(ReviewerApplication).filter_by(status='approved').all()
            for application in reviewer_applications:
                user_id = application.user_id
                # 排除已经是管理员的审核员
                if user_id not in ADMIN_IDS:
                    user = session.query(User).filter_by(user_id=user_id).first()
                    if user:
                        recipient_data.append({
                            'user_id': user_id,
                            'wxpusher_uid': getattr(user, 'wxpusher_uid', None)
                        })
            
            # 发送Telegram通知
            submission_data = {
                'id': getattr(submission, 'id'),
                'user_id': getattr(submission, 'user_id'),
                'username': getattr(submission, 'username'),
                'type': getattr(submission, 'type'),
                'content': getattr(submission, 'content')[:200] + "..." if len(getattr(submission, 'content')) > 200 else getattr(submission, 'content'),
                'file_id': getattr(submission, 'file_id'),
                'file_ids': json.loads(getattr(submission, 'file_ids', '[]')) if hasattr(submission, 'file_ids') and getattr(submission, 'file_ids', None) else [],
                'tags': json.loads(getattr(submission, 'tags', '[]')) if hasattr(submission, 'tags') and getattr(submission, 'tags', None) else [],
                'status': getattr(submission, 'status'),
                'category': getattr(submission, 'category'),
                'anonymous': getattr(submission, 'anonymous'),
                'cover_index': getattr(submission, 'cover_index') or 0,
                'timestamp': getattr(submission, 'timestamp')
            }
            
        # 构造通知文本
        is_business = submission_data['category'] == "business"
        submission_type = submission_data['type']
        content = submission_data['content']
        is_anonymous = submission_data['anonymous']
        tags = submission_data['tags']
        username = submission_data['username']
        submission_id = submission_data['id']
        
        tags_text = f"\n🏷️ 标签: {', '.join(tags)}" if tags else ""
        
        # 优化文本截断逻辑
        content_preview = content[:300] + ('...' if len(content) > 300 else '')
        
        text = (
            f"📬 {'商务合作' if is_business else '新投稿'} #{submission_id}\n"
            f"类型: {submission_type}\n"
            f"用户: @{username}\n\n"
            f"内容:\n{content_preview}{tags_text}"
        )
        
        if not is_business and is_anonymous:
            text += "\n\n👤 此投稿为匿名投稿"
        
        # 批量发送通知给所有管理员和审核员
        await _send_notifications_to_recipients(context, submission_data, [r['user_id'] for r in recipient_data])
        
        # 发送PushPlus通知
        from utils.pushplus import pushplus_notify
        if submission_data['category'] == 'business':
            pushplus_notify("business", submission_id)
        else:
            pushplus_notify("submission", submission_id)
            
        # 发送WxPusher通知
        from utils.wxpusher import wxpusher_notify
        wxpusher_uids = [r['wxpusher_uid'] for r in recipient_data if r['wxpusher_uid']]
        if wxpusher_uids:
            if submission_data['category'] == 'business':
                wxpusher_notify("business", submission_id, wxpusher_uids)
            else:
                wxpusher_notify("submission", submission_id, wxpusher_uids)
        
    except Exception as e:
        logger.error(f"通知管理员失败: {e}")
        # 备用机制：使用简化的通知方法
        await _notify_admins_fallback(context, submission_id)

async def _send_notifications_to_recipients(context, submission_data, recipient_ids):
    """发送通知给所有接收者 - 内部函数"""
    
    is_business = submission_data['category'] == "business"
    submission_type = submission_data['type']
    content = submission_data['content']
    file_ids = submission_data['file_ids']
    file_id = submission_data['file_id']
    is_anonymous = submission_data['anonymous']
    tags = submission_data['tags']
    username = submission_data['username']
    submission_id = submission_data['id']
    
    is_multi_media = submission_type in ["photo", "video"] and file_ids and len(file_ids) > 1
    
    tags_text = f"\n🏷️ 标签: {', '.join(tags)}" if tags else ""
    
    # 优化文本截断逻辑
    content_preview = content[:300] + ('...' if len(content) > 300 else '')
    
    text = (
        f"📬 {'商务合作' if is_business else '新投稿'} #{submission_id}\n"
        f"类型: {submission_type}\n"
        f"用户: @{username}\n\n"
        f"内容:\n{content_preview}{tags_text}"
    )
    
    if not is_business and is_anonymous:
        text += "\n\n👤 此投稿为匿名投稿"
    
    # 使用传入的接收者列表
    recipients = set(recipient_ids)
    
    # 批量发送通知
    await _batch_send_notifications(context, recipients, submission_data, text, is_business, is_anonymous, is_multi_media, tags)

async def _batch_send_notifications(context, recipients, submission_data, text, is_business, is_anonymous, is_multi_media, tags):
    """批量发送通知 - 内部函数"""
    submission_id = submission_data['id']
    submission_type = submission_data['type']
    file_ids = submission_data['file_ids']
    file_id = submission_data['file_id']
    
    # 检测是否为混合媒体投稿
    is_mixed_media = False
    if is_multi_media and 'file_types' in submission_data and submission_data['file_types']:
        file_types = submission_data['file_types'] if isinstance(submission_data['file_types'], list) else []
        has_photos = 'photo' in file_types
        has_videos = 'video' in file_types
        is_mixed_media = has_photos and has_videos
    
    # 预计算键盘布局，传递submission_data参数以支持查看媒体按钮
    keyboard = review_panel_menu(
        submission_data['id'], 
        submission_data['username'], 
        submission_data['anonymous'],
        submission_data  # 传递submission_data参数以支持查看媒体按钮
    )
    
    successful_sends = 0
    failed_sends = 0
    
    for recipient_id in recipients:
        try:
            if submission_type in ["photo", "video"] and file_ids:
                if submission_type == "photo":
                    await context.bot.send_photo(
                        chat_id=recipient_id,
                        photo=file_ids[0],
                        caption=text,
                        reply_markup=keyboard
                    )
                else:  # video
                    await context.bot.send_video(
                        chat_id=recipient_id,
                        video=file_ids[0],
                        caption=text,
                        reply_markup=keyboard
                    )
            elif submission_type == "photo" and file_id:
                await context.bot.send_photo(
                    chat_id=recipient_id,
                    photo=file_id,
                    caption=text,
                    reply_markup=keyboard
                )
            elif submission_type == "video" and file_id:
                await context.bot.send_video(
                    chat_id=recipient_id,
                    video=file_id,
                    caption=text,
                    reply_markup=keyboard
                )
            else:
                await context.bot.send_message(
                    chat_id=recipient_id,
                    text=text,
                    reply_markup=keyboard
                )
            successful_sends += 1
            logger.info(f"成功发送通知给用户 {recipient_id}")
        except Exception as e:
            failed_sends += 1
            logger.warning(f"发送通知给 {recipient_id} 失败: {e}")
            # 继续发送给其他接收者，不中断整个过程
    
    logger.info(f"通知发送完成 - 成功: {successful_sends}, 失败: {failed_sends}")
    
    # PushPlus通知
    from utils.pushplus import pushplus_notify
    if submission_data['category'] == 'business':
        pushplus_notify("business", submission_id)
    else:
        pushplus_notify("submission", submission_id)

async def _notify_admins_fallback(context, submission_id):
    """备用通知方法 - 确保系统正常运行
    
    当优化通知失败时使用的简化通知方法
    
    Args:
        context: Telegram context 对象
        submission_id: 投稿ID
    """
    try:
        from database import db
        with db.session_scope() as session:
            from database import Submission
            submission = session.query(Submission).filter_by(id=submission_id).first()
            if not submission:
                logger.error(f"备用通知: 投稿 {submission_id} 不存在")
                return
            
            # 简化的通知内容
            text = (
                f"📬 新投稿 #{submission_id}\n"
                f"类型: {submission.type}\n"
                f"用户: @{submission.username}\n\n"
                f"内容: {submission.content[:200]}..."
            )
            
            # 只向管理员发送简化通知
            successful_sends = 0
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=text
                    )
                    successful_sends += 1
                except Exception as e:
                    logger.error(f"备用通知发送失败 {admin_id}: {e}")
            
            logger.info(f"备用通知完成 - 成功: {successful_sends}/{len(ADMIN_IDS)}")
            
    except Exception as fallback_error:
        logger.critical(f"备用通知也失败: {fallback_error}")

async def notify_business_admins(context, submission_id):
    """通知管理员有新的商务合作
    
    Args:
        context: Telegram context 对象
        submission_id: 投稿ID
    """
    # 在会话范围内获取所有需要的信息
    from database import db
    with db.session_scope() as session:
        from database import Submission
        submission = session.query(Submission).filter_by(id=submission_id).first()
        if not submission:
            return
        
        # 提取所有需要的信息
        content = submission.content
        username = submission.username
        user_id = submission.user_id
    
    text = (
        f"📩 新商务合作请求 #{submission_id}\n"
        f"用户: @{username} (ID: {user_id})\n\n"
        f"合作详情:\n{content}\n\n"
        f"请及时处理！"
    )
    
    # 获取所有审核员
    from handlers.admin import is_reviewer
    reviewers = []
    session = db.get_session()
    try:
        from database import ReviewerApplication
        applications = session.query(ReviewerApplication).filter_by(status='approved').all()
        for app in applications:
            reviewers.append(app.user_id)
    except Exception as e:
        logger.error(f"获取审核员列表失败: {e}")
    finally:
        session.close()
    
    # 通知所有管理员和审核员
    recipients = set(ADMIN_IDS + reviewers)
    
    for recipient_id in recipients:
        try:
            await context.bot.send_message(
                chat_id=recipient_id,
                text=text,
                reply_markup=review_panel_menu(submission_id)
            )
        except Exception as e:
            logger.error(f"通知管理员/审核员失败: {e}")
    
    # 同时发送到审核群
    try:
        await context.bot.send_message(
            chat_id=MANAGEMENT_GROUP_ID,
            text=text,
            reply_markup=review_panel_menu(submission_id)
        )
    except Exception as e:
        logger.error(f"发送到审核群失败: {e}")
    
    # PushPlus通知
    from utils.pushplus import pushplus_notify
    pushplus_notify("business", submission_id)

async def publish_submission(context, submission_data):
    """发布投稿到频道和群组
    
    Args:
        context: Telegram context 对象
        submission_data: 投稿数据字典
    """
    # 导入配置以获取调试模式设置
    from config import DEBUG_MODE, DEBUG_CHANNEL_ID, DEBUG_GROUP_ID, ENABLED_CHANNEL_IDS, ENABLED_GROUP_IDS
    import asyncio
    
    # 获取标签
    tags = submission_data['tags']
    tags_text = f"\n\n🏷️ #{' #'.join(tags)}" if tags else ""

    # 检查是否有自定义关键词（在审核时输入的）
    custom_keyword = submission_data.get('custom_keyword', '关键词')
    # 添加关键词提示文本，使用占位符或实际关键词（暂时移除加粗格式以排除问题）
    keyword_prompt = f"\n\n💬 评论区【{custom_keyword}】"
    
    if submission_data['anonymous']:
        caption = f"{submission_data['content']}{tags_text}{keyword_prompt}"
    else:
        caption = f"{submission_data['content']}{tags_text}{keyword_prompt}\n\n👤 @{submission_data['username']}"
    
    # 限制caption长度以避免Telegram的4096字符限制
    if len(caption) > 4096:
        # 优先保留关键词提示行
        available_length = 4096 - len(keyword_prompt) - 10  # 预留一些空间
        caption = f"{submission_data['content'][:available_length]}{keyword_prompt}"
        if not submission_data['anonymous']:
            caption += f"\n\n👤 @{submission_data['username']}"
    
    published_message_ids = []
    published_group_message_ids = []
    
    logger.info(f"开始发布投稿 #{submission_data.get('id', 'Unknown')}, 类型: {submission_data.get('type', 'Unknown')}")
    
    try:
        # 如果启用了调试模式，将投稿发送到调试频道和调试群组
        if DEBUG_MODE:
            try:
                # 发布到调试频道
                if submission_data['type'] == "text":
                    await context.bot.send_message(
                        chat_id=DEBUG_CHANNEL_ID,
                        text=caption
                    )
                elif submission_data['type'] in ["photo", "video", "media"]:
                    # 对于媒体类型投稿，检查file_ids还是file_id
                    if submission_data.get('file_ids'):
                        file_id = submission_data['file_ids'][0]
                    else:
                        file_id = submission_data.get('file_id')
                    
                    if file_id:
                        # 检查媒体类型
                        if submission_data['type'] == "photo" or (submission_data['type'] == "media" and "photo" in submission_data.get('file_types', [])):
                            await context.bot.send_photo(
                                chat_id=DEBUG_CHANNEL_ID,
                                photo=file_id,
                                caption=caption
                            )
                        else:  # video or media with video
                            await context.bot.send_video(
                                chat_id=DEBUG_CHANNEL_ID,
                                video=file_id,
                                caption=caption
                            )
                
                # 发布到调试群组
                if submission_data['type'] == "text":
                    await context.bot.send_message(
                        chat_id=DEBUG_GROUP_ID,
                        text=caption
                    )
                elif submission_data['type'] in ["photo", "video", "media"]:
                    # 对于媒体类型投稿，检查file_ids还是file_id
                    if submission_data.get('file_ids'):
                        file_id = submission_data['file_ids'][0]
                    else:
                        file_id = submission_data.get('file_id')
                    
                    if file_id:
                        # 检查媒体类型
                        if submission_data['type'] == "photo" or (submission_data['type'] == "media" and "photo" in submission_data.get('file_types', [])):
                            await context.bot.send_photo(
                                chat_id=DEBUG_GROUP_ID,
                                photo=file_id,
                                caption=caption
                            )
                        else:  # video or media with video
                            await context.bot.send_video(
                                chat_id=DEBUG_GROUP_ID,
                                video=file_id,
                                caption=caption
                            )
                        
            except Exception as e:
                logger.error(f"调试模式发布投稿失败: {e}")
    
        # 原有的发布逻辑
        if submission_data['category'] == "business":
            return
    
        # 多媒体投稿处理（图片或视频）- 包括media类型
        if submission_data['type'] in ["photo", "video", "media"] and (submission_data.get('file_ids') or submission_data.get('file_id')):
            # 统一处理file_ids和file_id
            file_ids = submission_data.get('file_ids', [])
            if not file_ids and submission_data.get('file_id'):
                file_ids = [submission_data['file_id']]
            
            if file_ids:
                # 确定封面索引
                cover_index = submission_data['cover_index'] if submission_data['cover_index'] < len(file_ids) else 0
                cover_file_id = file_ids[cover_index]
                
                # 确定封面文件类型
                cover_media_type = submission_data['type']
                if submission_data['type'] == "media":
                    # 根据file_types确定媒体类型
                    file_types = submission_data.get('file_types', [])
                    if file_types and cover_index < len(file_types):
                        cover_media_type = file_types[cover_index]
                    else:
                        # 默认为photo
                        cover_media_type = "photo"
                
                # 1. 发布首媒体到所有频道（排除调试频道）
                channels_to_publish = [cid for cid in ENABLED_CHANNEL_IDS if str(cid) != str(DEBUG_CHANNEL_ID)]
                logger.info(f"准备发布到以下频道: {channels_to_publish}")
                for channel_id in channels_to_publish:
                    try:
                        logger.info(f"正在尝试发布到频道 {channel_id}")
                        if cover_media_type == "photo":
                            message = await context.bot.send_photo(
                                chat_id=channel_id,
                                photo=cover_file_id,
                                caption=caption
                            )
                            published_message_ids.append(str(message.message_id))
                            logger.info(f"成功发布图片到频道 {channel_id}, 消息ID: {message.message_id}")
                        else:  # video
                            message = await context.bot.send_video(
                                chat_id=channel_id,
                                video=cover_file_id,
                                caption=caption
                            )
                            published_message_ids.append(str(message.message_id))
                            logger.info(f"成功发布视频到频道 {channel_id}, 消息ID: {message.message_id}")
                    except Exception as e:
                        logger.error(f"发布到频道 {channel_id} 失败: {e}")
                        # 添加更详细的错误信息
                        logger.error(f"频道ID: {channel_id}, 错误类型: {type(e).__name__}")
                        # 检查机器人是否在频道中以及是否有发布权限
                        try:
                            chat_member = await context.bot.get_chat_member(chat_id=channel_id, user_id=(await context.bot.get_me()).id)
                            logger.info(f"机器人在频道 {channel_id} 中的角色: {chat_member.status}")
                            if chat_member.status not in ['administrator', 'creator']:
                                logger.error(f"机器人在频道 {channel_id} 中没有管理员权限")
                        except Exception as perm_error:
                            logger.error(f"检查机器人在频道 {channel_id} 中的权限失败: {perm_error}")
                        
                        # 不抛出异常，继续发布到其他频道
                
                # 2. 等待10秒让频道消息同步到关联的群组
                await asyncio.sleep(10)
                
                # 保存已发布消息的ID到数据库
                save_published_message_ids(submission_data['id'], published_message_ids, published_group_message_ids)
                logger.info(f"投稿发布完成，频道消息ID: {published_message_ids}, 群组消息ID: {published_group_message_ids}")
                return
        
        # 非多媒体的情况：发布到所有频道（排除调试频道）
        channels_to_publish = [cid for cid in ENABLED_CHANNEL_IDS if str(cid) != str(DEBUG_CHANNEL_ID)]
        logger.info(f"准备发布到以下频道: {channels_to_publish}")
        for channel_id in channels_to_publish:
            try:
                logger.info(f"正在尝试发布到频道 {channel_id}")
                if submission_data['type'] == "text":
                    message = await context.bot.send_message(
                        chat_id=channel_id,
                        text=caption
                    )
                    published_message_ids.append(str(message.message_id))
                    logger.info(f"成功发布文本到频道 {channel_id}, 消息ID: {message.message_id}")
                elif submission_data['type'] == "photo":
                    message = await context.bot.send_photo(
                        chat_id=channel_id,
                        photo=submission_data['file_id'],
                        caption=caption
                    )
                    published_message_ids.append(str(message.message_id))
                    logger.info(f"成功发布图片到频道 {channel_id}, 消息ID: {message.message_id}")
                elif submission_data['type'] == "video":
                    message = await context.bot.send_video(
                        chat_id=channel_id,
                        video=submission_data['file_id'],
                        caption=caption
                    )
                    published_message_ids.append(str(message.message_id))
                    logger.info(f"成功发布视频到频道 {channel_id}, 消息ID: {message.message_id}")
            except Exception as e:
                logger.error(f"发布到频道 {channel_id} 失败: {e}")
                # 添加更详细的错误信息
                logger.error(f"频道ID: {channel_id}, 错误类型: {type(e).__name__}")
                # 检查机器人是否在频道中以及是否有发布权限
                try:
                    chat_member = await context.bot.get_chat_member(chat_id=channel_id, user_id=(await context.bot.get_me()).id)
                    logger.info(f"机器人在频道 {channel_id} 中的角色: {chat_member.status}")
                    if chat_member.status not in ['administrator', 'creator']:
                        logger.error(f"机器人在频道 {channel_id} 中没有管理员权限")
                except Exception as perm_error:
                    logger.error(f"检查机器人在频道 {channel_id} 中的权限失败: {perm_error}")
                
                # 不抛出异常，继续发布到其他频道
        
        # 保存已发布消息的ID到数据库
        save_published_message_ids(submission_data['id'], published_message_ids, published_group_message_ids)
        logger.info(f"投稿发布完成，频道消息ID: {published_message_ids}, 群组消息ID: {published_group_message_ids}")
        
    except Exception as e:
        logger.error(f"发布投稿失败: {e}")
        logger.error(f"投稿ID: {submission_data.get('id', 'Unknown')}, 类型: {submission_data.get('type', 'Unknown')}")
        # 不抛出异常，避免整个流程中断

def save_published_message_ids(submission_id, published_message_ids, published_group_message_ids):
    """保存发布消息的ID到数据库
    
    Args:
        submission_id: 投稿ID
        published_message_ids: 频道中发布的消息ID列表
        published_group_message_ids: 群组中发布的消息ID列表
    """
    try:
        from database import db
        with db.session_scope() as session:
            from database import Submission
            submission = session.query(Submission).filter_by(id=submission_id).first()
            if submission:
                if published_message_ids:
                    # 保存第一个频道的消息ID到旧字段（兼容性）
                    setattr(submission, 'published_message_id', published_message_ids[0] if published_message_ids else None)
                    # 保存所有频道的消息ID到新字段
                    setattr(submission, 'published_channel_message_ids', json.dumps(published_message_ids))
                if published_group_message_ids:
                    setattr(submission, 'published_group_message_ids', json.dumps(published_group_message_ids))  # 保存群组消息ID列表
                # 不需要显式调用commit，session_scope上下文管理器会自动处理
                logger.info(f"已保存投稿 #{submission_id} 的发布消息ID")
    except Exception as e:
        logger.error(f"保存发布消息ID失败: {e}")

async def _publish_separated_media_groups(context, group_id, main_message_id, file_ids, cover_index, primary_type):
    """发布分离的媒体组（将照片和视频分成不同的媒体组）
    
    照片将分成最多10个媒体组发布（每组最多10张照片）
    视频将分成最多2个媒体组发布（每组最多10个视频）
    
    Args:
        context: Telegram context 对象
        group_id: 群组ID
        main_message_id: 主消息ID（可能为None）
        file_ids: 文件ID列表
        cover_index: 封面索引
        primary_type: 主要类型
        
    Returns:
        list: 已发布消息的ID列表
    """
    published_message_ids = []
    
    try:
        # 获取所有文件信息来判断类型
        photos = []
        videos = []
        
        for i, file_id in enumerate(file_ids):
            # 不再跳过封面，让首图也包含在群组媒体组中
            # if i == cover_index:  # 跳过封面，已经在主消息中发布
            #     continue
                
            try:
                # 尝试获取文件信息来判断类型
                file_obj = await context.bot.get_file(file_id)
                file_path = file_obj.file_path or ""
                
                # 根据文件路径或扩展名判断类型
                if any(ext in file_path.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    photos.append(file_id)
                elif any(ext in file_path.lower() for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']):
                    videos.append(file_id)
                else:
                    # 如果无法判断，根据主类型分类
                    if primary_type == "photo":
                        photos.append(file_id)
                    else:
                        videos.append(file_id)
            except Exception as e:
                logger.warning(f"无法获取文件信息 {file_id}: {e}")
                # 默认按主类型分类
                if primary_type == "photo":
                    photos.append(file_id)
                else:
                    videos.append(file_id)
        
        # 发布照片组（如果有）- 最多10个媒体组，每组最多10张照片
        if photos:
            # 将照片分成多个媒体组，每组最多10张，最多10组
            max_photo_groups = 10
            for i in range(0, min(len(photos), max_photo_groups * 10), 10):
                photo_group = photos[i:i+10]  # 每组最多10张照片
                media_group = []
                for photo_id in photo_group:
                    media_group.append(InputMediaPhoto(media=photo_id))
                
                if media_group:
                    # 如果有主消息ID，则回复该消息，否则直接发送
                    if main_message_id:
                        messages = await context.bot.send_media_group(
                            chat_id=group_id,
                            media=media_group,
                            reply_to_message_id=main_message_id
                        )
                    else:
                        messages = await context.bot.send_media_group(
                            chat_id=group_id,
                            media=media_group
                        )
                    # 收集已发布消息的ID
                    for message in messages:
                        published_message_ids.append(message.message_id)
                    logger.info(f"已向群组 {group_id} 发送第 {i//10 + 1} 组照片，共 {len(media_group)} 张")
        
        # 发布视频组（如果有）- 最多2个媒体组，每组最多10个视频
        if videos:
            # 将视频分成多个媒体组，每组最多10个，最多2组
            max_video_groups = 2
            for i in range(0, min(len(videos), max_video_groups * 10), 10):
                video_group = videos[i:i+10]  # 每组最多10个视频
                media_group = []
                for video_id in video_group:
                    media_group.append(InputMediaVideo(media=video_id))
                
                if media_group:
                    # 如果有主消息ID，则回复该消息，否则直接发送
                    if main_message_id:
                        messages = await context.bot.send_media_group(
                            chat_id=group_id,
                            media=media_group,
                            reply_to_message_id=main_message_id
                        )
                    else:
                        messages = await context.bot.send_media_group(
                            chat_id=group_id,
                            media=media_group
                        )
                    # 收集已发布消息的ID
                    for message in messages:
                        published_message_ids.append(message.message_id)
                    logger.info(f"已向群组 {group_id} 发送第 {i//10 + 1} 组视频，共 {len(media_group)} 个")
                
    except Exception as e:
        logger.error(f"发布分离媒体组失败: {e}")
    
    return published_message_ids

async def show_submission(context, submission_data, chat_id, index, total):
    """显示待审投稿详情
    
    Args:
        context: Telegram context 对象
        submission_data: 投稿数据字典
        chat_id: 聊天ID
        index: 当前索引
        total: 总投稿数
    """
    is_business = submission_data['category'] == "business"
    type_name = "商务合作" if is_business else {
        "text": "文本",
        "photo": "图片",
        "video": "视频"
    }.get(submission_data['type'], "投稿")
    
    # 获取标签
    tags = submission_data['tags']
    
    anonymous_text = " [匿名]" if submission_data['anonymous'] else ""
    tags_text = f"\n🏷️ 标签: {', '.join(tags)}" if tags else ""
    
    text = (
        f"📬 #{submission_data['id']} {type_name}投稿{anonymous_text}\n"
        f"用户: @{submission_data['username']} (ID: {submission_data['user_id']})\n"
        f"时间: {submission_data['timestamp']}\n\n"
    )
    
    if is_business:
        text += f"合作详情:\n{submission_data['content']}{tags_text}"
    else:
        text += f"内容:\n{submission_data['content'][:300]}{'...' if len(submission_data['content']) > 300 else ''}{tags_text}"
    
    # 判断是否为多媒体投稿和混合媒体投稿
    is_multi_media = submission_data['type'] in ["photo", "video"] and submission_data['file_ids'] and len(submission_data['file_ids']) > 1
    
    # 检测是否为混合媒体投稿（包含照片和视频）
    is_mixed_media = False
    if is_multi_media and 'file_types' in submission_data and submission_data['file_types']:
        file_types = submission_data['file_types'] if isinstance(submission_data['file_types'], list) else []
        has_photos = 'photo' in file_types
        has_videos = 'video' in file_types
        is_mixed_media = has_photos and has_videos
    
    # 准备键盘布局，传递submission_data参数
    keyboard = []
    # 将InlineKeyboardMarkup中的按钮复制到可变列表中
    review_menu = review_panel_menu(
        submission_data['id'], 
        submission_data['username'], 
        submission_data['anonymous'],
        submission_data  # 传递submission_data参数以支持查看媒体按钮
    )
    for row in review_menu.inline_keyboard:  # type: ignore
        keyboard.append(list(row))
    
    # 添加分页导航按钮
    nav_buttons = []
    if index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ 上一条", callback_data=f"review_{index-1}"))
    
    # 添加页码显示和跳转功能
    nav_buttons.append(InlineKeyboardButton(f"{index+1}/{total}", callback_data="noop"))
    
    if index < total - 1:
        nav_buttons.append(InlineKeyboardButton("下一条 ➡️", callback_data=f"review_{index+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # 添加跳转到指定页面的按钮（仅当总数超过10时显示）
    if total > 10:
        keyboard.append([InlineKeyboardButton("🔢 跳转到页面", callback_data=f"jump_to_page_review_{index}_{total}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if submission_data['type'] in ["photo", "video"] and submission_data['file_ids']:
            file_ids = submission_data['file_ids']
            if file_ids:
                if submission_data['type'] == "photo":
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=file_ids[0],
                        caption=text,
                        reply_markup=reply_markup
                    )
                else:  # video
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=file_ids[0],
                        caption=text,
                        reply_markup=reply_markup
                    )
                return
        elif submission_data['type'] == "photo" and submission_data['file_id']:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=submission_data['file_id'],
                caption=text,
                reply_markup=reply_markup
            )
            return
        elif submission_data['type'] == "video" and submission_data['file_id']:
            await context.bot.send_video(
                chat_id=chat_id,
                video=submission_data['file_id'],
                caption=text,
                reply_markup=reply_markup
            )
            return
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"发送投稿详情失败: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{text}\n\n⚠️ 无法加载媒体文件",
            reply_markup=reply_markup
        )

async def show_history_submission(context, submission_data, chat_id, index, total):
    """显示历史投稿详情
    
    Args:
        context: Telegram context 对象
        submission_data: 投稿数据字典
        chat_id: 聊天ID
        index: 当前索引
        total: 总投稿数
    """
    from database import db
    
    is_business = submission_data['category'] == "business"
    type_name = "商务合作" if is_business else {
        "text": "文本",
        "photo": "图片",
        "video": "视频"
    }.get(submission_data['type'], "投稿")
    
    # 获取标签
    tags = submission_data['tags']
    
    status_icon = "✅" if submission_data['status'] == 'approved' else "❌" if submission_data['status'] == 'rejected' else "⏳"
    anonymous_text = " [匿名]" if submission_data['anonymous'] else ""
    tags_text = f"\n🏷️ 标签: {', '.join(tags)}" if tags else ""
    
    # 获取审核者信息
    handler_info = ""
    if submission_data['status'] in ['approved', 'rejected'] and submission_data.get('handled_by'):
        try:
            # 使用with语句确保会话正确管理
            with db.session_scope() as session:
                from database import User
                handler_user = session.query(User).filter(User.user_id == submission_data['handled_by']).first()
                
                if handler_user:
                    action_text = "通过" if submission_data['status'] == 'approved' else "拒绝"
                    handler_name = handler_user.username or handler_user.first_name or f"用户{submission_data['handled_by']}"
                    handler_info = f"\n👤 审核者: @{handler_name} ({action_text})"
                    if submission_data.get('handled_at'):
                        handler_info += f"\n📅 审核时间: {submission_data['handled_at']}"
                else:
                    action_text = "通过" if submission_data['status'] == 'approved' else "拒绝"
                    handler_info = f"\n👤 审核者: 用户{submission_data['handled_by']} ({action_text})"
        except Exception as e:
            logger.error(f"获取审核者信息失败: {e}")
            action_text = "通过" if submission_data['status'] == 'approved' else "拒绝"
            handler_info = f"\n👤 审核者: 用户{submission_data['handled_by']} ({action_text})"
    
    text = (
        f"{status_icon} #{submission_data['id']} {type_name}投稿{anonymous_text}\n"
        f"用户: @{submission_data['username']} (ID: {submission_data['user_id']})\n"
        f"时间: {submission_data['timestamp']}\n"
        f"状态: {'已通过' if submission_data['status'] == 'approved' else '已拒绝' if submission_data['status'] == 'rejected' else '待审核'}{handler_info}\n\n"
    )
    
    if is_business:
        text += f"合作详情:\n{submission_data['content']}{tags_text}"
    else:
        text += f"内容:\n{submission_data['content'][:300]}{'...' if len(submission_data['content']) > 300 else ''}{tags_text}"
    
    # 显示拒绝原因（如果有）
    if submission_data['status'] == 'rejected' and submission_data.get('reject_reason'):
        text += f"\n\n❌ 拒绝原因: {submission_data['reject_reason']}"
    
    # 判断是否为多媒体投稿和混合媒体投稿
    is_multi_media = submission_data['type'] in ["photo", "video"] and submission_data['file_ids'] and len(submission_data['file_ids']) > 1
    
    # 检测是否为混合媒体投稿（包含照片和视频）
    is_mixed_media = False
    if is_multi_media and 'file_types' in submission_data and submission_data['file_types']:
        file_types = submission_data['file_types'] if isinstance(submission_data['file_types'], list) else []
        has_photos = 'photo' in file_types
        has_videos = 'video' in file_types
        is_mixed_media = has_photos and has_videos
    
    # 准备键盘布局，传递submission_data参数
    keyboard = []
    # 将InlineKeyboardMarkup中的按钮复制到可变列表中
    history_menu = history_review_panel_menu(
        submission_data['id'], 
        submission_data['username'], 
        submission_data['anonymous'],
        submission_data
    )
    for row in history_menu.inline_keyboard:  # type: ignore
        keyboard.append(list(row))
    
    # 添加分页导航按钮
    nav_buttons = []
    if index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ 上一条", callback_data=f"history_{index-1}"))
    
    # 添加页码显示和跳转功能
    nav_buttons.append(InlineKeyboardButton(f"{index+1}/{total}", callback_data="noop"))
    
    if index < total - 1:
        nav_buttons.append(InlineKeyboardButton("下一条 ➡️", callback_data=f"history_{index+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # 添加跳转到指定页面的按钮（仅当总数超过10时显示）
    if total > 10:
        keyboard.append([InlineKeyboardButton("🔢 跳转到页面", callback_data=f"jump_to_page_history_{index}_{total}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if submission_data['type'] in ["photo", "video"] and submission_data['file_ids']:
            file_ids = submission_data['file_ids']
            if file_ids:
                # 验证第一个文件ID是否有效
                first_file_id = file_ids[0]
                if first_file_id and isinstance(first_file_id, str) and len(first_file_id) > 0:
                    if submission_data['type'] == "photo":
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=first_file_id,
                            caption=text,
                            reply_markup=reply_markup
                        )
                    else:  # video
                        await context.bot.send_video(
                            chat_id=chat_id,
                            video=first_file_id,
                            caption=text,
                            reply_markup=reply_markup
                        )
                    return
                else:
                    # 文件ID无效，发送纯文本消息
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"{text}\n\n⚠️ 无法加载媒体文件（文件ID无效）",
                        reply_markup=reply_markup
                    )
                    return
        elif submission_data['type'] == "photo" and submission_data['file_id']:
            # 验证文件ID是否有效
            file_id = submission_data['file_id']
            if file_id and isinstance(file_id, str) and len(file_id) > 0:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=file_id,
                    caption=text,
                    reply_markup=reply_markup
                )
            else:
                # 文件ID无效，发送纯文本消息
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"{text}\n\n⚠️ 无法加载媒体文件（文件ID无效）",
                    reply_markup=reply_markup
                )
            return
        elif submission_data['type'] == "video" and submission_data['file_id']:
            # 验证文件ID是否有效
            file_id = submission_data['file_id']
            if file_id and isinstance(file_id, str) and len(file_id) > 0:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=file_id,
                    caption=text,
                    reply_markup=reply_markup
                )
            else:
                # 文件ID无效，发送纯文本消息
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"{text}\n\n⚠️ 无法加载媒体文件",
                    reply_markup=reply_markup
                )
            return
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"发送投稿详情失败: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{text}\n\n⚠️ 无法加载媒体文件",
            reply_markup=reply_markup
        )

def check_user_bot_blocked(context, user_id):
    """
    检测用户是否删除或屏蔽了机器人
    
    通过尝试向用户发送一条简单的消息来检测用户是否删除或屏蔽了机器人。
    如果发送失败并出现Forbidden异常，则认为用户已删除或屏蔽了机器人。
    
    Args:
        context: Telegram context 对象
        user_id: 用户ID
        
    Returns:
        bool: True表示用户已删除或屏蔽机器人，False表示用户正常
    """
    try:
        # 尝试向用户发送一条简单的消息
        # 使用send_chat_action而不是send_message，因为这样不会打扰用户
        context.bot.send_chat_action(chat_id=user_id, action="typing")
        return False  # 如果成功发送，说明用户没有屏蔽机器人
    except Exception as e:
        error_msg = str(e)
        # 检查是否是Forbidden异常，这通常表示用户删除或屏蔽了机器人
        if "Forbidden" in error_msg or "bot was blocked by the user" in error_msg or "user is deactivated" in error_msg:
            logger.info(f"用户 {user_id} 已删除或屏蔽了机器人: {error_msg}")
            # 更新数据库中的用户状态
            try:
                from database import db
                db.update_user_bot_blocked(user_id, True)
            except Exception as db_error:
                logger.error(f"更新用户 {user_id} 的机器人状态失败: {db_error}")
            return True
        else:
            # 其他类型的错误，不认为是用户屏蔽了机器人
            logger.warning(f"检测用户 {user_id} 状态时出现其他错误: {error_msg}")
            return False
