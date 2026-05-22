import sys
from pathlib import Path

# pytest.ini_options sets pythonpath = ["src"], but this ensures the path
# is available when tests are run directly (e.g. python -m pytest from root).
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
