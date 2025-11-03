async def _admin_pending_fallback(update: Update, context: CallbackContext):
    """管理员面板备用方法 - 确保系统正常运行
    
    当优化方法失败时，回退到原始实现
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    try:
        with db.session_scope() as session:
            from database import Submission
            pending = session.query(Submission).filter_by(status='pending').limit(20).all()
            
            if not pending:
                await query.answer()
                await query.edit_message_text(
                    "🎉 没有待审稿件！",
                    reply_markup=back_button("admin_panel")
                )
                return
            
            pending_data = []
            for submission in pending:
                try:
                    file_ids = json.loads(getattr(submission, 'file_ids', '[]')) if getattr(submission, 'file_ids') else []
                except:
                    file_ids = []
                    
                try:
                    tags = json.loads(getattr(submission, 'tags', '[]')) if getattr(submission, 'tags') else []
                except:
                    tags = []
                    
                try:
                    file_types = json.loads(getattr(submission, 'file_types', '[]')) if hasattr(submission, 'file_types') and getattr(submission, 'file_types') else []
                except:
                    file_types = []
                    
                submission_data = {
                    'id': getattr(submission, 'id'),
                    'user_id': getattr(submission, 'user_id'),
                    'username': getattr(submission, 'username'),
                    'type': getattr(submission, 'type'),
                    'content': getattr(submission, 'content'),
                    'file_id': getattr(submission, 'file_id'),
                    'file_ids': file_ids,
                    'file_types': file_types,
                    'tags': tags,
                    'status': getattr(submission, 'status'),
                    'category': getattr(submission, 'category'),
                    'anonymous': getattr(submission, 'anonymous'),
                    'cover_index': getattr(submission, 'cover_index') or 0,
                    'reject_reason': getattr(submission, 'reject_reason'),
                    'handled_by': getattr(submission, 'handled_by'),
                    'handled_at': getattr(submission, 'handled_at'),
                    'timestamp': getattr(submission, 'timestamp')
                }
                pending_data.append(submission_data)
        
        if context.user_data is not None:
            context.user_data['pending_submissions'] = pending_data
            context.user_data['current_index'] = 0
        
        await show_submission(context, pending_data[0], user.id, 0, len(pending_data))
        logger.info("使用备用方法成功处理管理员面板请求")
        
    except Exception as fallback_error:
        logger.error(f"备用方法也失败: {fallback_error}")
        await query.answer("系统错误，请稍后再试", show_alert=True)