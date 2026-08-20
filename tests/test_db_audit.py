import unittest

from tests._env import setup_test_environment

setup_test_environment()

from src.cli.db_audit import collect_database_audit
from src.db import Base, SessionLocal, engine
from src.seed import seed_defaults


class DatabaseAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_defaults(db)

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_audit_returns_only_aggregate_schema_safety_facts(self) -> None:
        with SessionLocal() as db:
            report = collect_database_audit(db)

        self.assertEqual(report["alembic_revision"], "unavailable")
        self.assertEqual(report["enrollment_integrity"], {
            "course_version_mismatches": 0,
            "invalid_progress_rows": 0,
        })
        self.assertEqual(report["learning_structure"]["module_based_course_versions"], 2)
        self.assertEqual(report["learning_structure"]["flat_compatibility_course_versions"], 1)
        self.assertEqual(report["learning_structure"]["flat_compatibility_enrollments"], 0)
        self.assertEqual(report["rag_index_jobs"], {"queued": 12})


if __name__ == "__main__":
    unittest.main()
