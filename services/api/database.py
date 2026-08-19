from pathlib import Path
from tinydb import TinyDB

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "suppliers_db.json"

db = TinyDB(DB_PATH)
suppliers_table = db.table("suppliers")
users_table = db.table("users")
