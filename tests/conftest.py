import logging
import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# tests/test_app_helpers.py imports src/app.py directly to reach a handful
# of pure, Streamlit-independent helper functions. Doing that outside a
# real `streamlit run` session makes Streamlit's own runtime log a
# "missing ScriptRunContext! This warning can be ignored when running in
# bare mode." line (harmless - confirmed by hand before adding that test
# file) for every such call during collection/import. Raised to ERROR here
# purely to keep `pytest -q` output readable; does not affect what the
# tests check.
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").setLevel(logging.ERROR)
