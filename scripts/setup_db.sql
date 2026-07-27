-- setup_db.sql — schema for PostgreSQL database `ricescanner`
-- Rice Disease Handheld Scanner. Run against the ricescanner DB.

-- Scan sessions: one row per field scan event.
CREATE TABLE IF NOT EXISTS scan_sessions (
    id              SERIAL PRIMARY KEY,
    started_at      TIMESTAMP DEFAULT NOW(),
    location_notes  TEXT,
    plant_condition VARCHAR(50),
    gps_lat         FLOAT,
    gps_lon         FLOAT
);

-- RGB camera scans.
CREATE TABLE IF NOT EXISTS rgb_scans (
    id                 SERIAL PRIMARY KEY,
    session_id         INT REFERENCES scan_sessions(id),
    image_path         TEXT NOT NULL,
    prediction         VARCHAR(50),
    confidence         FLOAT,
    processing_time_ms FLOAT,
    captured_at        TIMESTAMP DEFAULT NOW()
);

-- NIR (NoIR) camera scans. Same as rgb_scans plus ndvi_value.
CREATE TABLE IF NOT EXISTS nir_scans (
    id                 SERIAL PRIMARY KEY,
    session_id         INT REFERENCES scan_sessions(id),
    image_path         TEXT NOT NULL,
    prediction         VARCHAR(50),
    confidence         FLOAT,
    processing_time_ms FLOAT,
    ndvi_value         FLOAT,
    captured_at        TIMESTAMP DEFAULT NOW()
);

-- Electrochemical biosensor (DPV) readings.
CREATE TABLE IF NOT EXISTS biosensor_readings (
    id                   SERIAL PRIMARY KEY,
    session_id           INT REFERENCES scan_sessions(id),
    dpv_peak_current_ua  FLOAT,
    dpv_peak_voltage_v   FLOAT,
    re_voltage_v         FLOAT,
    raw_adc_values       JSONB,
    reading_time_ms      FLOAT,
    captured_at          TIMESTAMP DEFAULT NOW()
);

-- Late-fusion final diagnoses.
CREATE TABLE IF NOT EXISTS fused_diagnoses (
    id               SERIAL PRIMARY KEY,
    session_id       INT REFERENCES scan_sessions(id),
    rgb_prediction   VARCHAR(50),
    rgb_confidence   FLOAT,
    nir_prediction   VARCHAR(50),
    nir_confidence   FLOAT,
    biosensor_signal FLOAT,
    final_diagnosis  VARCHAR(50),
    final_confidence FLOAT,
    diagnosed_at     TIMESTAMP DEFAULT NOW()
);

-- Device telemetry / system logs.
CREATE TABLE IF NOT EXISTS system_logs (
    id                SERIAL PRIMARY KEY,
    cpu_temp_c        FLOAT,
    memory_usage_pct  FLOAT,
    battery_voltage_v FLOAT,
    uptime_seconds    INT,
    logged_at         TIMESTAMP DEFAULT NOW()
);
