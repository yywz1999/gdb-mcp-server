.PHONY: all clean install run-server run-example setup

all: setup

setup: examples/test_program
	@echo "Setup complete. Run 'make run-server' to start the server."

examples/test_program: examples/test_program.c
	gcc -g examples/test_program.c -o examples/test_program

install:
	pip install -r requirements.txt

run-server:
	python3 mcp_server.py

run-example:
	python3 examples/debug_demo.py

clean:
	rm -f examples/test_program
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete 