import sys
import types
import importlib
import pandas as pd

# Provide a minimal stub for streamlit so the component module can import
sys.modules.setdefault("streamlit", types.SimpleNamespace())
# Map 'crud' to 'app.crud' so component's absolute import works in tests
sys.modules.setdefault("crud", importlib.import_module("app.crud"))

from app.components.manual_asset_manager import _build_state_from_editor, Col


def test_build_state_from_editor_basic_mapping():
    # Given a simple df with two existing rows
    df = pd.DataFrame(
        {
            Col.ID.value: [101, 202],
            Col.NAME.value: ["A", "B"],
        }
    )

    raw_state = {
        "deleted_rows": [1],  # row index 1 -> ID 202
        "edited_rows": {"0": {"수량": 400}},  # row index 0 -> ID 101
        "added_rows": [{"이름": "C"}],
    }

    enriched = _build_state_from_editor(df, raw_state)

    assert enriched["deleted_ids"] == [202]
    assert enriched["edited_by_id"] == {"101": {"수량": 400}}
    assert enriched["added_rows"] == [{"이름": "C"}]


def test_build_state_from_editor_empty_state():
    df = pd.DataFrame({Col.ID.value: [1, 2]})
    raw_state = {}
    enriched = _build_state_from_editor(df, raw_state)
    assert enriched == {"added_rows": [], "deleted_ids": [], "edited_by_id": {}}
