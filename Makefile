PY := .venv/bin

.PHONY: install test test-slow dashboard site

install:
	python3.12 -m venv .venv
	$(PY)/pip install -q -e ../rag-studio/backend -e ".[dev]"
	@if [ -f dashboard/package.json ]; then npm --prefix dashboard install; fi

test:
	$(PY)/pytest -q

test-slow:
	$(PY)/pytest -q -m slow

dashboard:
	$(PY)/evallab export
	npm --prefix dashboard run dev

site:
	$(PY)/evallab export
	npm --prefix dashboard run build
