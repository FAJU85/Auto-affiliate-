"""
Session-start QA hook.

When pytest collects test_qa_suite.py (e.g. `make qa`), the banner below
reminds that this suite is the first gate — all 82 tests must be green
before any feature work proceeds.
"""



def pytest_collection_finish(session):
    qa_items = [i for i in session.items if "test_qa_suite" in str(i.fspath)]
    if qa_items:
        print(
            f"\n{'='*60}\n"
            f"  QA AUTOMATION SUITE  —  {len(qa_items)} session-start checks\n"
            f"  All must pass before feature work begins.\n"
            f"{'='*60}\n"
        )
