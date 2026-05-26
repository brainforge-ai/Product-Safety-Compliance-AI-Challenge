"""
Pytest configuration and fixtures.

Sets up path for src imports and provides common fixtures.
"""
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
