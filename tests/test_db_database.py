"""Tests for SQLAlchemy engine helpers (coverage for app.db.database)."""

import app.db.database as dbmod


def _restore_engine(saved_e, saved_s):
    cur = dbmod._engine
    if cur is not None and cur is not saved_e:
        cur.dispose()
    dbmod._engine, dbmod.SessionLocal = saved_e, saved_s


def test_init_db_engine_idempotent():
    saved_e, saved_s = dbmod._engine, dbmod.SessionLocal
    try:
        dbmod._engine = None
        dbmod.SessionLocal = None
        e1 = dbmod.init_db_engine()
        e2 = dbmod.init_db_engine()
        assert e1 is e2
        assert dbmod.SessionLocal is not None
    finally:
        _restore_engine(saved_e, saved_s)


def test_get_engine_uses_singleton():
    saved_e, saved_s = dbmod._engine, dbmod.SessionLocal
    try:
        dbmod._engine = None
        dbmod.SessionLocal = None
        dbmod.init_db_engine()
        g1 = dbmod.get_engine()
        g2 = dbmod.get_engine()
        assert g1 is g2
    finally:
        _restore_engine(saved_e, saved_s)


def test_get_db_yields_session_and_closes():
    saved_e, saved_s = dbmod._engine, dbmod.SessionLocal
    try:
        dbmod._engine = None
        dbmod.SessionLocal = None
        dbmod.init_db_engine()
        gen = dbmod.get_db()
        sess = next(gen)
        assert sess is not None
        gen.close()
    finally:
        _restore_engine(saved_e, saved_s)


def test_check_db_connection():
    saved_e, saved_s = dbmod._engine, dbmod.SessionLocal
    try:
        dbmod._engine = None
        dbmod.SessionLocal = None
        dbmod.check_db_connection()
    finally:
        _restore_engine(saved_e, saved_s)
