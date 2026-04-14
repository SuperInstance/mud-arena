# MUD Arena Build System

# Detect CUDA
CUDA := $(shell which nvcc 2>/dev/null)

.PHONY: all gpu cpu python clean test

all: python
gpu: mud-arena
cpu: mud-arena-cpu

# GPU build (Jetson Orin / CUDA 12.6)
mud-arena: src/mud_arena.cu
	nvcc -O3 -arch=sm_87 -o mud-arena src/mud_arena.cu

# CPU fallback (any system)
mud-arena-cpu: src/mud_arena.cu
	gcc -DCPU_ONLY -O3 -o mud-arena-cpu src/mud_arena.cu -lm -lpthread

# Python tools
python:
	pip install -r requirements.txt 2>/dev/null || true

# Run evolution
evolve:
	python3 src/evolve.py --generations 100 --population 200 --scenarios 20

# Run server
server:
	python3 src/server.py

# Run dashboard
dashboard:
	python3 src/dashboard.py --output dashboard.html

# Test
test:
	python3 -m pytest tests/ -v

clean:
	rm -f mud-arena mud-arena-cpu dashboard.html
	rm -rf __pycache__ .mypy_cache
