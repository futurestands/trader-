PY=python
PIP=$(PY) -m pip

.PHONY: test run lint

test:
	$(PIP) install --upgrade pip
	$(PIP) install -r python_engine/requirements.txt
	$(PIP) install pytest pytest-asyncio
	pytest -v

run:
	$(PY) python_engine/main.py

lint:
	$(PIP) install black flake8
	black --check python_engine || true
	flake8 python_engine || true
