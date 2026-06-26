.PHONY: help install data test ui api web lint docker clean

help:
	@echo "MediGraph AI — common tasks"
	@echo "  make install   Install dependencies"
	@echo "  make data      (Re)generate the bundled synthetic dataset"
	@echo "  make test      Run the test suite"
	@echo "  make ui        Launch the Streamlit clinical workspace (:8501)"
	@echo "  make api       Launch the REST/FHIR API (:8000, docs at /docs)"
	@echo "  make web       Refresh demo data and serve the website (:8088)"
	@echo "  make docker    Build the Docker image"

install:
	pip install -r requirements.txt

data:
	python -m medigraph.data.generator

test:
	python -m pytest -q

ui:
	streamlit run ui/streamlit_app.py

api:
	uvicorn medigraph.api.main:app --reload

web:
	python scripts/export_web_demo.py
	@echo "Serving website at http://localhost:8088"
	cd website && python -m http.server 8088

lint:
	ruff check medigraph tests || true

docker:
	docker build -t medigraph-ai .

clean:
	rm -rf .runtime .pytest_cache **/__pycache__
