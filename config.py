import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()  # Load .env file

# --- Paths ---
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
CHROMA_DIR = BASE_DIR / ".chromadb"

# --- LLM ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_API_BASE = os.getenv("LLM_API_BASE", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = 0.1 
LLM_MAX_TOKENS = int(os.getenv("MAX_LENGTH", "32000"))

# --- RAG ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RAG_TOP_K = 5
RAG_CHUNK_SIZE = 500
RAG_CHUNK_OVERLAP = 50

# --- Policy Thresholds ---
AUTO_REFUND_LIMIT = 500000  # VNĐ — hoàn tiền dưới mức này được tự động duyệt
MAX_AUTO_REFUNDS_90_DAYS = 2  # Số lần hoàn tiền tự động tối đa trong 90 ngày
REFUND_ELIGIBILITY_DAYS = 30  # Số ngày sau thanh toán được phép hoàn tiền
DELIVERY_DELAY_THRESHOLD_DAYS = 3  # Số ngày quá hạn giao = "trễ"
HIGH_VALUE_ORDER_THRESHOLD = 1000000  # VNĐ — đơn hàng trên mức này cần duyệt

# --- Agent ---
MAX_TOOL_CALLS_PER_TURN = 5
CURRENT_DATE = datetime.now().strftime("%Y-%m-%d")
