import os
import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from models.models import Base

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 데이터베이스 연결 정보
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# 데이터베이스 URL 생성
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy 엔진 생성
engine = create_engine(DATABASE_URL)

# 세션 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session():
    """데이터베이스 세션을 반환하는 함수"""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        logger.error(f"데이터베이스 세션 생성 실패: {e}")
        db.close()
        raise


def test_connection():
    """데이터베이스 연결을 테스트하는 함수"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "데이터베이스 연결 성공"
    except Exception as e:
        logger.error(f"데이터베이스 연결 테스트 실패: {e}")
        return False, f"데이터베이스 연결 실패: {str(e)}"


def initialize_db(drop_all=True):
    """데이터베이스 초기화 함수

    Args:
        drop_all (bool): True인 경우 기존 테이블을 모두 삭제하고 다시 생성
    """
    try:
        # 이미 존재하는 테이블 확인
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        if drop_all and existing_tables:
            # 기존 테이블 삭제
            logger.info("기존 테이블을 삭제합니다...")
            Base.metadata.drop_all(bind=engine)
            logger.info("기존 테이블이 삭제되었습니다.")

        Base.metadata.create_all(bind=engine)
        logger.info("스키마 동기화 완료.")

        # 테이블 목록 출력
        tables = inspect(engine).get_table_names()
        logger.info(f"현재 테이블 목록: {', '.join(tables)}")

    except Exception as e:
        logger.error(f"데이터베이스 초기화 실패: {e}")
        raise
