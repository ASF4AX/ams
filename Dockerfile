# Python 3.11 이미지 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치를 위한 requirements.txt 복사
COPY requirements.txt .

# Python 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY app/ ./app/
COPY models/ ./app/models/

# 환경 변수 설정
ENV PYTHONPATH=/app

# Streamlit 실행 스크립트 생성
RUN echo '#!/bin/bash\n\
streamlit run app/app.py \
--server.port=8501 \
--server.address=0.0.0.0 \
--server.baseUrlPath=${STREAMLIT_BASE_URL_PATH}' > /app/start.sh && \
chmod +x /app/start.sh

# 실행 스크립트 실행
CMD ["/app/start.sh"] 