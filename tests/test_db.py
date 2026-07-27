"""test_db.py — database read/write via SQLAlchemy.

Attempts to connect to PostgreSQL `ricescanner`; if unreachable, falls back to
an in-memory SQLite database for a schema smoke test. Skips gracefully when
SQLAlchemy is not installed.
"""
import os

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")

from sqlalchemy import (  # noqa: E402
    Column, Float, ForeignKey, Integer, String, create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker  # noqa: E402

Base = declarative_base()


class ScanSession(Base):
    __tablename__ = "scan_sessions"
    id = Column(Integer, primary_key=True)
    location_notes = Column(String)
    plant_condition = Column(String(50))
    gps_lat = Column(Float)
    gps_lon = Column(Float)


class FusedDiagnosis(Base):
    __tablename__ = "fused_diagnoses"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("scan_sessions.id"))
    final_diagnosis = Column(String(50))
    final_confidence = Column(Float)


PG_URL = os.environ.get(
    "RICESCANNER_DB_URL",
    "postgresql+psycopg2://scanner_user@localhost/ricescanner",
)


def _make_engine():
    """Prefer PostgreSQL; fall back to in-memory SQLite if unreachable."""
    try:
        eng = create_engine(PG_URL)
        conn = eng.connect()
        conn.close()
        return eng, "postgresql"
    except Exception:  # noqa: BLE001
        return create_engine("sqlite:///:memory:"), "sqlite"


@pytest.fixture(scope="module")
def engine():
    eng, backend = _make_engine()
    # For the SQLite smoke test we create the schema; on real PG the tables
    # already exist from setup_db.sql, but create_all is a no-op if present.
    Base.metadata.create_all(eng)
    yield eng
    if backend == "sqlite":
        Base.metadata.drop_all(eng)


def test_write_and_read(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        sess = ScanSession(
            location_notes="paddy A", plant_condition="rice_blast",
            gps_lat=14.6, gps_lon=121.0,
        )
        s.add(sess)
        s.flush()  # assigns id without committing to shared PG state

        diag = FusedDiagnosis(
            session_id=sess.id, final_diagnosis="rice_blast",
            final_confidence=0.87,
        )
        s.add(diag)
        s.flush()

        got = s.query(FusedDiagnosis).filter_by(session_id=sess.id).one()
        assert got.final_diagnosis == "rice_blast"
        assert got.final_confidence == pytest.approx(0.87)
    finally:
        s.rollback()  # never persist test rows into a real DB
        s.close()


def test_schema_has_expected_tables(engine):
    from sqlalchemy import inspect
    names = set(inspect(engine).get_table_names())
    # At minimum the SQLAlchemy models we declared must exist.
    assert {"scan_sessions", "fused_diagnoses"}.issubset(names)
