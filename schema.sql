-- Run this in your Supabase SQL editor

CREATE TABLE users (
    telegram_id BIGINT PRIMARY KEY,
    name TEXT,
    rank TEXT,
    battalion TEXT NOT NULL,
    coy TEXT NOT NULL,
    default_officer TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE reports (
    id TEXT PRIMARY KEY,
    filed_by BIGINT REFERENCES users(telegram_id),
    type TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    serviceman_name TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    location TEXT NOT NULL,
    battalion TEXT NOT NULL,
    coy TEXT NOT NULL,
    ops_impact TEXT DEFAULT 'NIL',
    causal_a TEXT DEFAULT 'NIL',
    causal_b TEXT DEFAULT 'NIL',
    causal_c TEXT DEFAULT 'NIL',
    verbal_report TEXT,
    written_report TEXT,
    follow_up_date DATE,
    raw_dump TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE versions (
    id SERIAL PRIMARY KEY,
    report_id TEXT REFERENCES reports(id),
    version_number INT NOT NULL,
    brief_description TEXT NOT NULL,
    follow_up_action TEXT DEFAULT 'NIL',
    reporting_officer TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
