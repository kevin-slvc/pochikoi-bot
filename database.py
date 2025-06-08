import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool

# データベースURL（環境変数から取得）
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# PostgreSQL URLの修正（RailwayのURLは古い形式の場合がある）
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# エンジンの作成
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,  # Railway環境での接続プール問題を回避
    echo=False
)

# セッションの設定
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# ベースクラス
Base = declarative_base()

class User(Base):
    """ユーザーモデル"""
    __tablename__ = 'users'
    
    user_id = Column(String(255), primary_key=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # オンボーディング情報
    name = Column(String(100))
    gender = Column(String(20))
    birthday = Column(String(50))
    onboarding_stage = Column(Integer, default=0)
    onboarding_complete = Column(Boolean, default=False)
    
    # 恋愛情報
    relationship_status = Column(String(50))
    main_concern = Column(String(50))
    
    # 占い情報（JSON形式で保存）
    sanmeigaku = Column(Text)  # JSON
    animal_character = Column(Text)  # JSON
    palm_analysis = Column(Text)
    palm_uploaded_at = Column(DateTime)
    
    # サブスクリプション情報
    is_premium = Column(Boolean, default=False)
    subscription_start = Column(DateTime)
    subscription_end = Column(DateTime)
    
    # その他のデータ（拡張用）
    extra_data = Column(Text)  # JSON

    def to_dict(self):
        """辞書形式に変換"""
        return {
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'name': self.name,
            'gender': self.gender,
            'birthday': self.birthday,
            'onboarding_stage': self.onboarding_stage,
            'onboarding_complete': self.onboarding_complete,
            'relationship_status': self.relationship_status,
            'main_concern': self.main_concern,
            'sanmeigaku': json.loads(self.sanmeigaku) if self.sanmeigaku else None,
            'animal_character': json.loads(self.animal_character) if self.animal_character else None,
            'palm_analysis': self.palm_analysis,
            'palm_uploaded_at': self.palm_uploaded_at.isoformat() if self.palm_uploaded_at else None,
            'is_premium': self.is_premium,
            'extra_data': json.loads(self.extra_data) if self.extra_data else {}
        }

    @classmethod
    def from_dict(cls, user_id, data):
        """辞書形式から作成"""
        user = cls(user_id=user_id)
        
        # 基本情報
        user.name = data.get('name')
        user.gender = data.get('gender')
        user.birthday = data.get('birthday')
        user.onboarding_stage = data.get('onboarding_stage', 0)
        user.onboarding_complete = data.get('onboarding_complete', False)
        
        # 恋愛情報
        user.relationship_status = data.get('relationship_status')
        user.main_concern = data.get('main_concern')
        
        # 占い情報
        if data.get('sanmeigaku'):
            user.sanmeigaku = json.dumps(data['sanmeigaku'], ensure_ascii=False)
        if data.get('animal_character'):
            user.animal_character = json.dumps(data['animal_character'], ensure_ascii=False)
        user.palm_analysis = data.get('palm_analysis')
        
        # 日付変換
        if data.get('created_at'):
            try:
                user.created_at = datetime.fromisoformat(data['created_at'].replace('Z', ''))
            except:
                pass
        
        if data.get('palm_uploaded_at'):
            try:
                user.palm_uploaded_at = datetime.fromisoformat(data['palm_uploaded_at'].replace('Z', ''))
            except:
                pass
        
        # サブスクリプション
        user.is_premium = data.get('is_premium', False)
        
        return user

class DatabaseManager:
    """データベース操作を管理するクラス"""
    
    @staticmethod
    def init_db():
        """データベースの初期化"""
        try:
            Base.metadata.create_all(bind=engine)
            print("Database tables created successfully!")
            return True
        except Exception as e:
            print(f"Database initialization error: {e}")
            return False
    
    @staticmethod
    def get_user(user_id):
        """ユーザー情報を取得"""
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user:
                return user.to_dict()
            return None
        finally:
            session.close()
    
    @staticmethod
    def save_user(user_id, user_data):
        """ユーザー情報を保存"""
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.user_id == user_id).first()
            
            if user:
                # 既存ユーザーの更新
                for key, value in user_data.items():
                    if key in ['sanmeigaku', 'animal_character'] and isinstance(value, dict):
                        setattr(user, key, json.dumps(value, ensure_ascii=False))
                    elif key == 'created_at':
                        continue  # created_atは更新しない
                    elif hasattr(user, key):
                        setattr(user, key, value)
                user.updated_at = datetime.now()
            else:
                # 新規ユーザーの作成
                user = User.from_dict(user_id, user_data)
                session.add(user)
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Save user error: {e}")
            return False
        finally:
            session.close()
    
    @staticmethod
    def get_all_users():
        """全ユーザーを取得"""
        session = SessionLocal()
        try:
            users = session.query(User).all()
            return {user.user_id: user.to_dict() for user in users}
        finally:
            session.close()
    
    @staticmethod
    def delete_user(user_id):
        """ユーザーを削除"""
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user:
                session.delete(user)
                session.commit()
                return True
            return False
        finally:
            session.close()
    
    @staticmethod
    def get_premium_users():
        """有料会員のみを取得"""
        session = SessionLocal()
        try:
            users = session.query(User).filter(User.is_premium == True).all()
            return {user.user_id: user.to_dict() for user in users}
        finally:
            session.close()
    
    @staticmethod
    def migrate_from_json(json_file_path='users_data.json'):
        """JSONファイルからデータを移行"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
            
            migrated_count = 0
            for user_id, user_data in old_data.items():
                if DatabaseManager.save_user(user_id, user_data):
                    migrated_count += 1
            
            print(f"Migrated {migrated_count} users from JSON to PostgreSQL")
            return migrated_count
        except Exception as e:
            print(f"Migration error: {e}")
            return 0

# データベース初期化を実行
if __name__ == "__main__":
    if DatabaseManager.init_db():
        print("Database initialized successfully!")
        # JSONからの移行を実行
        DatabaseManager.migrate_from_json()
