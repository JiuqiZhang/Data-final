"""Add backend/ to sys.path so service modules are importable without installation."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
