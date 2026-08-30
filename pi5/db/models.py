"""SQLAlchemy 2.0 ORM models for the rice scanner database.

JSONB is used for Postgres; the type falls back to generic JSON on other
backends (e.g. SQLite in tests) so the models remain portable.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.types import JSON

# Use JSONB on Postgres, plain JSON elsewhere.
JSONType = JSONB().with_variant(JSON(), "sqlite")


class Base(DeclarativeBase):
    pass


class ScanSession(Base):
    __tablename__ = "scan_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    location_notes: Mapped[Optional[str]] = mapped_column(String(512))
    plant_condition: Mapped[Optional[str]] = mapped_column(String(128))
    gps_lat: Mapped[Optional[float]] = mapped_column(Float)
    gps_lon: Mapped[Optional[float]] = mapped_column(Float)

    rgb_scans: Mapped[list["RGBScan"]] = relationship(back_populates="session")
    nir_scans: Mapped[list["NIRScan"]] = relationship(back_populates="session")
    biosensor_readings: Mapped[list["BiosensorReading"]] = relationship(
        back_populates="session"
    )
    fused_diagnoses: Mapped[list["FusedDiagnosis"]] = relationship(
        back_populates="session"
    )


class RGBScan(Base):
    __tablename__ = "rgb_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("scan_sessions.id"))
    image_path: Mapped[Optional[str]] = mapped_column(String(512))
    prediction: Mapped[Optional[str]] = mapped_column(String(64))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    processing_time_ms: Mapped[Optional[float]] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped["ScanSession"] = relationship(back_populates="rgb_scans")


class NIRScan(Base):
    __tablename__ = "nir_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("scan_sessions.id"))
    image_path: Mapped[Optional[str]] = mapped_column(String(512))
    ndvi_value: Mapped[Optional[float]] = mapped_column(Float)
    prediction: Mapped[Optional[str]] = mapped_column(String(64))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    processing_time_ms: Mapped[Optional[float]] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped["ScanSession"] = relationship(back_populates="nir_scans")


class BiosensorReading(Base):
    __tablename__ = "biosensor_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("scan_sessions.id"))
    dpv_peak_current_ua: Mapped[Optional[float]] = mapped_column(Float)
    dpv_peak_voltage_v: Mapped[Optional[float]] = mapped_column(Float)
    re_voltage_v: Mapped[Optional[float]] = mapped_column(Float)
    raw_adc_values: Mapped[Optional[dict]] = mapped_column(JSONType)
    reading_time_ms: Mapped[Optional[float]] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped["ScanSession"] = relationship(
        back_populates="biosensor_readings"
    )


class FusedDiagnosis(Base):
    __tablename__ = "fused_diagnoses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("scan_sessions.id"))
    rgb_prediction: Mapped[Optional[str]] = mapped_column(String(64))
    rgb_confidence: Mapped[Optional[float]] = mapped_column(Float)
    nir_prediction: Mapped[Optional[str]] = mapped_column(String(64))
    nir_confidence: Mapped[Optional[float]] = mapped_column(Float)
    biosensor_signal: Mapped[Optional[float]] = mapped_column(Float)
    final_diagnosis: Mapped[Optional[str]] = mapped_column(String(64))
    final_confidence: Mapped[Optional[float]] = mapped_column(Float)
    # True when any contributing subsystem was mocked. Persisted so simulated
    # rows can never be mistaken for field data during validation.
    mock: Mapped[bool] = mapped_column(Boolean, default=False,
                                       server_default=text("false"))
    degraded: Mapped[Optional[str]] = mapped_column(Text)
    diagnosed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped["ScanSession"] = relationship(
        back_populates="fused_diagnoses"
    )


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cpu_temp_c: Mapped[Optional[float]] = mapped_column(Float)
    memory_usage_pct: Mapped[Optional[float]] = mapped_column(Float)
    battery_voltage_v: Mapped[Optional[float]] = mapped_column(Float)
    uptime_seconds: Mapped[Optional[float]] = mapped_column(Float)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


if __name__ == "__main__":
    for table in Base.metadata.sorted_tables:
        print(table.name, [c.name for c in table.columns])
