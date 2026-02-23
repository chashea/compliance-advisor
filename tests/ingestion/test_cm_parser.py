"""Tests for ingestion.cm_parser — validation, parsing, upsert."""
from unittest.mock import patch, MagicMock
import pytest
import pandas as pd
import numpy as np

VALID_UUID = "11111111-1111-1111-1111-111111111111"


def _make_valid_df(rows=3):
    return pd.DataFrame({
        "Action": [f"Action {i}" for i in range(rows)],
        "Points achieved": [5.0] * rows,
        "Max points": [10.0] * rows,
        "Regulation": ["SOC 2"] * rows,
        "Category": ["Identity"] * rows,
        "Status": ["Implemented"] * rows,
    })


class TestInputValidation:
    def test_invalid_tenant_id_raises(self):
        from ingestion.cm_parser import parse_and_store
        with pytest.raises(ValueError, match="UUID"):
            parse_and_store("not-a-uuid", b"data")

    def test_non_bytes_raises_type_error(self):
        from ingestion.cm_parser import parse_and_store
        with pytest.raises(TypeError, match="bytes"):
            parse_and_store(VALID_UUID, "string")

    def test_oversized_file_raises(self):
        from ingestion.cm_parser import parse_and_store
        huge = b"x" * (10 * 1024 * 1024 + 1)
        with pytest.raises(ValueError, match="exceeds maximum"):
            parse_and_store(VALID_UUID, huge)

    def test_invalid_excel_raises(self):
        from ingestion.cm_parser import parse_and_store
        with patch("ingestion.cm_parser.pd.read_excel", side_effect=Exception("corrupt")):
            with pytest.raises(ValueError, match="Could not parse"):
                parse_and_store(VALID_UUID, b"not-excel")

    def test_missing_required_columns_raises(self):
        df = pd.DataFrame({"Action": ["a"], "Notes": ["n"]})
        from ingestion.cm_parser import parse_and_store
        with patch("ingestion.cm_parser.pd.read_excel", return_value=df):
            with pytest.raises(ValueError, match="missing required columns"):
                parse_and_store(VALID_UUID, b"data")

    def test_too_many_rows_raises(self):
        df = _make_valid_df(10_001)
        from ingestion.cm_parser import parse_and_store
        with patch("ingestion.cm_parser.pd.read_excel", return_value=df):
            with pytest.raises(ValueError, match="10000"):
                parse_and_store(VALID_UUID, b"data")


class TestHappyPath:
    def test_returns_row_count(self, mock_connection):
        df = _make_valid_df(3)
        from ingestion.cm_parser import parse_and_store
        with patch("ingestion.cm_parser.pd.read_excel", return_value=df), \
             patch("ingestion.cm_parser.get_connection", return_value=mock_connection), \
             patch("ingestion.cm_parser.set_tenant_context"):
            result = parse_and_store(VALID_UUID, b"data")
        assert result == 3

    def test_calls_set_tenant_context(self, mock_connection):
        df = _make_valid_df(1)
        from ingestion.cm_parser import parse_and_store
        with patch("ingestion.cm_parser.pd.read_excel", return_value=df), \
             patch("ingestion.cm_parser.get_connection", return_value=mock_connection), \
             patch("ingestion.cm_parser.set_tenant_context") as mock_ctx:
            parse_and_store(VALID_UUID, b"data")
        mock_ctx.assert_called_once_with(mock_connection, VALID_UUID)

    def test_closes_connection_on_error(self, mock_connection):
        df = _make_valid_df(1)
        mock_connection.cursor.return_value.execute.side_effect = RuntimeError("db")
        from ingestion.cm_parser import parse_and_store
        with patch("ingestion.cm_parser.pd.read_excel", return_value=df), \
             patch("ingestion.cm_parser.get_connection", return_value=mock_connection), \
             patch("ingestion.cm_parser.set_tenant_context"):
            with pytest.raises(RuntimeError):
                parse_and_store(VALID_UUID, b"data")
        mock_connection.close.assert_called_once()

    def test_string_truncation(self, mock_connection):
        df = pd.DataFrame({
            "Action": ["x" * 400],
            "Points achieved": [5.0],
            "Max points": [10.0],
            "Regulation": ["SOC 2"],
        })
        from ingestion.cm_parser import parse_and_store
        with patch("ingestion.cm_parser.pd.read_excel", return_value=df), \
             patch("ingestion.cm_parser.get_connection", return_value=mock_connection), \
             patch("ingestion.cm_parser.set_tenant_context"):
            parse_and_store(VALID_UUID, b"data")

        cursor = mock_connection.cursor.return_value
        # action_name is arg index 1 (after tenant_id at index 0 in the execute params)
        call_args = cursor.execute.call_args[0]
        action_val = call_args[2]  # tenant_id, sql, then params start
        # The action should be truncated to 300 chars
        assert len(action_val) <= 300
