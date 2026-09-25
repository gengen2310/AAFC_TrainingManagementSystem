from app.config import normalize_database_url


def test_generic_postgresql_urls_use_repository_psycopg2_driver():
    assert normalize_database_url("postgres://db.example.test/tms") == (
        "postgresql+psycopg2://db.example.test/tms"
    )
    assert normalize_database_url("postgresql://db.example.test/tms") == (
        "postgresql+psycopg2://db.example.test/tms"
    )


def test_sqlite_urls_are_unchanged():
    assert normalize_database_url("sqlite:///./aafc_tms.db") == "sqlite:///./aafc_tms.db"
