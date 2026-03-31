from openkiln import db, config


def test_init_core_creates_database(openkiln_home):
    """init_core creates core.db and the skills directory."""
    db.init_core()
    assert (openkiln_home / "core.db").exists()
    assert (openkiln_home / "skills").exists()


def test_init_core_is_idempotent(openkiln_home):
    """init_core can be called multiple times without error."""
    db.init_core()
    db.init_core()  # should not raise
    assert (openkiln_home / "core.db").exists()


def test_check_connection_returns_false_before_init(openkiln_home):
    """check_connection returns False when core.db does not exist."""
    assert db.check_connection() is False


def test_check_connection_returns_true_after_init(openkiln_home):
    """check_connection returns True after init_core."""
    db.init_core()
    assert db.check_connection() is True


def test_core_schema_tables_exist(openkiln_home):
    """Core schema creates all expected tables."""
    db.init_core()
    with db.connection() as conn:
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "records" in tables
    assert "workflow_runs" in tables
    assert "installed_skills" in tables


def test_batch_read_yields_correct_batches(openkiln_home):
    """batch_read yields rows in batches of BATCH_SIZE."""
    db.init_core()

    # insert 25 records
    with db.transaction() as conn:
        conn.executemany(
            "INSERT INTO records (type) VALUES (?)",
            [("contact",)] * 25
        )

    # read with small batch size to verify batching
    original_batch_size = db.BATCH_SIZE
    db.BATCH_SIZE = 10

    batches = []
    with db.connection() as conn:
        for batch in db.batch_read(conn, "SELECT * FROM records"):
            batches.append(batch)

    db.BATCH_SIZE = original_batch_size

    assert len(batches) == 3           # 10 + 10 + 5
    assert len(batches[0]) == 10
    assert len(batches[1]) == 10
    assert len(batches[2]) == 5


def test_batch_write_inserts_rows(openkiln_home):
    """batch_write inserts rows via executemany."""
    db.init_core()
    with db.transaction() as conn:
        affected = db.batch_write(
            conn,
            "INSERT INTO records (type) VALUES (?)",
            [("contact",), ("company",), ("investor",)],
        )
    assert affected == 3

    with db.connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM records"
        ).fetchone()[0]
    assert count == 3


def test_transaction_rolls_back_on_error(openkiln_home):
    """transaction rolls back all writes if an error occurs."""
    db.init_core()

    try:
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO records (type) VALUES (?)", ("contact",)
            )
            raise RuntimeError("simulated failure")
    except RuntimeError:
        pass

    with db.connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM records"
        ).fetchone()[0]
    assert count == 0  # rolled back — nothing written
