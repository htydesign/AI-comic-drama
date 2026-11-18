.PHONY: dev debug

dev:
	uv run langgraph dev --allow-blocking --host 127.0.0.1 --port 80

debug:
	uv run langgraph dev --allow-blocking --host 127.0.0.1 --port 80 --debug-port 5678