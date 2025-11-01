# Mini-Raft Makefile
# Convenient commands for development and testing

.PHONY: help install test clean start stop watch status demo

help: ## Show this help message
	@echo "Mini-Raft Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt

test: ## Run all tests
	pytest test_raft.py -v --timeout=10

test-coverage: ## Run tests with coverage report
	pytest test_raft.py -v --cov=raft --cov=server --cov-report=html --cov-report=term

test-leader: ## Test leader election only
	pytest test_raft.py::TestLeaderElection -v

test-replication: ## Test log replication only
	pytest test_raft.py::TestLogReplication -v

test-safety: ## Test safety properties only
	pytest test_raft.py::TestSafetyProperties -v

clean: ## Clean up data and temporary files
	rm -rf data/
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -f start_cluster.sh
	find . -name "*.pyc" -delete

start: ## Generate and show cluster start script
	python cli.py start --nodes 5 --base-port 8000 --data-dir ./data
	@echo ""
	@echo "Run: ./start_cluster.sh"

start-3: ## Generate 3-node cluster
	python cli.py start --nodes 3 --base-port 8000 --data-dir ./data

start-5: ## Generate 5-node cluster
	python cli.py start --nodes 5 --base-port 8000 --data-dir ./data

start-7: ## Generate 7-node cluster
	python cli.py start --nodes 7 --base-port 8000 --data-dir ./data

stop: ## Stop all running nodes
	pkill -f "python.*run_node.py" || true

watch: ## Watch cluster status in real-time
	python cli.py watch --base-port 8000 --nodes 5 --refresh 1

status: ## Get current cluster status
	python cli.py status --base-port 8000 --nodes 5

demo: ## Run a quick demo
	@echo "Starting 3-node cluster for demo..."
	@$(MAKE) clean
	@$(MAKE) start-3
	@echo ""
	@echo "In another terminal, run: make watch"
	@echo "Then in a third terminal, run: make demo-requests"

demo-requests: ## Send demo client requests
	@echo "Setting some values..."
	sleep 2
	python -c "import asyncio; from cli import request; asyncio.run(request(8000, 'name', 'Alice', 'set'))"
	sleep 1
	python -c "import asyncio; from cli import request; asyncio.run(request(8000, 'age', '30', 'set'))"
	sleep 1
	python -c "import asyncio; from cli import request; asyncio.run(request(8000, 'city', 'Oslo', 'set'))"
	sleep 1
	@echo ""
	@echo "Getting values..."
	python -c "import asyncio; from cli import request; asyncio.run(request(8000, 'name', None, 'get'))"
	python -c "import asyncio; from cli import request; asyncio.run(request(8000, 'age', None, 'get'))"
	python -c "import asyncio; from cli import request; asyncio.run(request(8000, 'city', None, 'get'))"

chaos: ## Run chaos tests
	python cli.py chaos --base-port 8000 --nodes 5 --operations 50

format: ## Format code with black
	black raft.py server.py cli.py run_node.py test_raft.py

lint: ## Run linter
	python -m pylint raft.py server.py cli.py run_node.py || true

typecheck: ## Run type checker
	mypy raft.py server.py cli.py run_node.py --ignore-missing-imports || true

quality: format lint typecheck ## Run all quality checks

dev-setup: install ## Setup development environment
	@echo "Development environment ready!"
	@echo "Run 'make help' to see available commands"

docker-build: ## Build Docker image
	@echo "Docker support coming soon..."

all: clean install test ## Clean, install, and test

.DEFAULT_GOAL := help
