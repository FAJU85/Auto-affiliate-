.PHONY: qa qa-report qa-open test test-cov

ALLURE_RESULTS := /tmp/allure-results
ALLURE_REPORT  := /tmp/allure-report

# Run QA suite (session-start health check) + intelligent layer + Allure report
qa:
	python -m pytest api/tests/test_qa_suite.py api/tests/test_qa_intelligent.py -v \
		--alluredir=$(ALLURE_RESULTS) \
		--tb=short
	allure generate $(ALLURE_RESULTS) -o $(ALLURE_REPORT) --clean
	@echo ""
	@echo "✓ Allure report: $(ALLURE_REPORT)/index.html"

# Intelligent QA only (property tests + memory replay)
qa-intelligent:
	python -m pytest api/tests/test_qa_intelligent.py -v --tb=short

# Generate Allure report from last run (no re-run)
qa-report:
	allure generate $(ALLURE_RESULTS) -o $(ALLURE_REPORT) --clean

# Run full test suite with branch coverage
test:
	python -m pytest api/tests/ -q --tb=short

test-cov:
	python -m pytest api/tests/ \
		--cov=api --cov-branch \
		--cov-report=term-missing \
		--cov-fail-under=85 \
		-q --tb=short
