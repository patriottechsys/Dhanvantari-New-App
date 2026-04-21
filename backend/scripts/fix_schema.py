"""
Fix schema drift between migration 0001 and current models.
Adds missing columns to health_profiles and patients tables.

Run from backend/: python scripts/fix_schema.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)
DATABASE_URL = _db_url
engine = create_async_engine(DATABASE_URL)

# All columns to add using IF NOT EXISTS (safe to re-run)
HEALTH_PROFILES_COLUMNS = [
    # New lab columns (model uses these names, migration used different names)
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS cholesterol_total FLOAT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS hemoglobin FLOAT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS hematocrit FLOAT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS eosinophils_pct FLOAT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS glucose FLOAT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS egfr FLOAT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS testosterone FLOAT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS psa FLOAT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS lab_date DATE",
    # Ayurvedic fields (model uses these names)
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS dosha_primary VARCHAR(20)",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS dosha_secondary VARCHAR(20)",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS dosha_imbalances TEXT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS agni_assessment TEXT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS ama_assessment TEXT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS prakriti_notes TEXT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS vikriti_notes TEXT",
    # Clinical fields (model uses these names)
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS chief_complaints TEXT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS medical_history TEXT",
    "ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS current_medications TEXT",
]

PATIENTS_COLUMNS = [
    "ALTER TABLE patients ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
    "ALTER TABLE patients ADD COLUMN IF NOT EXISTS weight_note VARCHAR(200)",
    "ALTER TABLE patients ADD COLUMN IF NOT EXISTS alcohol_notes VARCHAR(200)",
    "ALTER TABLE patients ADD COLUMN IF NOT EXISTS caffeine_notes VARCHAR(200)",
]


async def fix_schema():
    async with engine.begin() as conn:
        print("Fixing health_profiles...")
        for sql in HEALTH_PROFILES_COLUMNS:
            await conn.execute(__import__("sqlalchemy").text(sql))
            col = sql.split("ADD COLUMN IF NOT EXISTS ")[1].split()[0]
            print(f"  + {col}")

        print("Fixing patients...")
        for sql in PATIENTS_COLUMNS:
            await conn.execute(__import__("sqlalchemy").text(sql))
            col = sql.split("ADD COLUMN IF NOT EXISTS ")[1].split()[0]
            print(f"  + {col}")

    print("\nSchema fix complete. Safe to re-run seed_demo.py now.")


if __name__ == "__main__":
    asyncio.run(fix_schema())
