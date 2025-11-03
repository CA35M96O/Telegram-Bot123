import sqlite3
import os

def upgrade_database():
    """手动升级数据库结构"""
    db_path = 'submissions.db'
    
    if not os.path.exists(db_path):
        print("数据库文件不存在")
        return False
    
    try:
        # 连接到数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查并创建所有表
        # users表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username VARCHAR(100),
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                is_bot BOOLEAN DEFAULT FALSE,
                language_code VARCHAR(10),
                wxpusher_uid VARCHAR(100),
                last_interaction DATETIME DEFAULT CURRENT_TIMESTAMP,
                first_interaction DATETIME DEFAULT CURRENT_TIMESTAMP,
                bot_blocked BOOLEAN DEFAULT FALSE,
                is_banned BOOLEAN DEFAULT FALSE
            )
        """)
        print("已检查/创建users表")
        
        # submissions表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                username VARCHAR(100) NOT NULL,
                type VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                file_id VARCHAR(200),
                file_ids TEXT DEFAULT '[]',
                file_types TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                status VARCHAR(20) DEFAULT 'pending',
                category VARCHAR(20) DEFAULT 'submission',
                anonymous BOOLEAN DEFAULT FALSE,
                cover_index INTEGER DEFAULT 0,
                reject_reason TEXT,
                handled_by INTEGER,
                handled_at DATETIME,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                published_message_id VARCHAR(100),
                published_channel_message_ids TEXT DEFAULT '[]',
                published_group_message_ids TEXT DEFAULT '[]',
                feedback_sent BOOLEAN DEFAULT FALSE,
                feedback_sent_at DATETIME
            )
        """)
        print("已检查/创建submissions表")
        
        # user_states表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state VARCHAR(50) NOT NULL,
                data TEXT DEFAULT '{}',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("已检查/创建user_states表")
        
        # reviewer_applications表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviewer_applications (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                username VARCHAR(100) NOT NULL,
                reason TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                handled_by INTEGER,
                handled_at DATETIME,
                invite_link VARCHAR(500),
                permissions TEXT DEFAULT '{}'
            )
        """)
        print("已检查/创建reviewer_applications表")
        
        # tags表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                name VARCHAR(50) PRIMARY KEY,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 0
            )
        """)
        print("已检查/创建tags表")
        
        # ban_records表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ban_records (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                banned_by INTEGER NOT NULL,
                reason TEXT,
                ban_type VARCHAR(20) DEFAULT 'temporary',
                ban_start DATETIME DEFAULT CURRENT_TIMESTAMP,
                ban_end DATETIME,
                unbanned_at DATETIME
            )
        """)
        print("已检查/创建ban_records表")
        
        # system_config表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                id INTEGER PRIMARY KEY,
                channel_ids TEXT DEFAULT '',
                group_ids TEXT DEFAULT '',
                disabled_channels TEXT DEFAULT '',
                disabled_groups TEXT DEFAULT ''
            )
        """)
        print("已检查/创建system_config表")
        
        # 检查并添加缺失的字段到现有表
        # users表字段检查
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        # 添加缺失的字段
        if 'wxpusher_uid' not in column_names:
            cursor.execute("ALTER TABLE users ADD COLUMN wxpusher_uid VARCHAR(100)")
            print("已添加wxpusher_uid字段到users表")
            
        if 'bot_blocked' not in column_names:
            cursor.execute("ALTER TABLE users ADD COLUMN bot_blocked BOOLEAN DEFAULT FALSE")
            print("已添加bot_blocked字段到users表")
            
        if 'is_banned' not in column_names:
            cursor.execute("ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT FALSE")
            print("已添加is_banned字段到users表")
        
        # submissions表字段检查
        cursor.execute("PRAGMA table_info(submissions)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        # 添加缺失的字段
        if 'file_types' not in column_names:
            cursor.execute("ALTER TABLE submissions ADD COLUMN file_types TEXT DEFAULT '[]'")
            print("已添加file_types字段到submissions表")
            
        if 'published_channel_message_ids' not in column_names:
            cursor.execute("ALTER TABLE submissions ADD COLUMN published_channel_message_ids TEXT DEFAULT '[]'")
            print("已添加published_channel_message_ids字段到submissions表")
            
        if 'published_group_message_ids' not in column_names:
            cursor.execute("ALTER TABLE submissions ADD COLUMN published_group_message_ids TEXT DEFAULT '[]'")
            print("已添加published_group_message_ids字段到submissions表")
            
        if 'feedback_sent' not in column_names:
            cursor.execute("ALTER TABLE submissions ADD COLUMN feedback_sent BOOLEAN DEFAULT FALSE")
            print("已添加feedback_sent字段到submissions表")
            
        if 'feedback_sent_at' not in column_names:
            cursor.execute("ALTER TABLE submissions ADD COLUMN feedback_sent_at DATETIME")
            print("已添加feedback_sent_at字段到submissions表")
        
        # reviewer_applications表字段检查
        cursor.execute("PRAGMA table_info(reviewer_applications)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        # 添加缺失的字段
        if 'permissions' not in column_names:
            cursor.execute("ALTER TABLE reviewer_applications ADD COLUMN permissions TEXT DEFAULT '{}'")
            print("已添加permissions字段到reviewer_applications表")
        
        # system_config表字段检查
        cursor.execute("PRAGMA table_info(system_config)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        # 添加缺失的字段
        if 'disabled_channels' not in column_names:
            cursor.execute("ALTER TABLE system_config ADD COLUMN disabled_channels TEXT DEFAULT ''")
            print("已添加disabled_channels字段到system_config表")
            
        if 'disabled_groups' not in column_names:
            cursor.execute("ALTER TABLE system_config ADD COLUMN disabled_groups TEXT DEFAULT ''")
            print("已添加disabled_groups字段到system_config表")
        
        # 创建索引
        # users表索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_last_interaction ON users (last_interaction)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_first_interaction ON users (first_interaction)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_bot_blocked ON users (bot_blocked)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_banned ON users (is_banned)")
        print("已检查/创建users表索引")
        
        # submissions表索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions (status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_user_id ON submissions (user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_timestamp ON submissions (timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_category ON submissions (category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_handled_by ON submissions (handled_by)")
        print("已检查/创建submissions表索引")
        
        # user_states表索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_states_timestamp ON user_states (timestamp)")
        print("已检查/创建user_states表索引")
        
        # reviewer_applications表索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviewer_status ON reviewer_applications (status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviewer_user_id ON reviewer_applications (user_id)")
        print("已检查/创建reviewer_applications表索引")
        
        # ban_records表索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ban_records_user_id ON ban_records (user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ban_records_ban_type ON ban_records (ban_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ban_records_ban_start ON ban_records (ban_start)")
        print("已检查/创建ban_records表索引")
        
        # 提交更改并关闭连接
        conn.commit()
        conn.close()
        
        print("数据库升级完成")
        return True
        
    except Exception as e:
        print(f"数据库升级失败: {e}")
        return False

if __name__ == "__main__":
    upgrade_database()