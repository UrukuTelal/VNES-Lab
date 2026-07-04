"""Tests for the Data Transformer."""

import os
import tempfile
import pytest

from rlaaer.data.transformer import Transformer, TransformationError


class TestTransformer:
    @pytest.fixture
    def transformer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            t = Transformer()
            t.transformed_dir = os.path.join(tmpdir, "transformed")
            os.makedirs(t.transformed_dir, exist_ok=True)
            yield t

    def test_identity(self, transformer):
        data = {"value": 42}
        result = transformer.transform(
            {"source": "test", "data": data},
            {"method": "identity"},
        )
        assert result["source"] == "test"
        assert result["transformed"]["value"] == 42

    def test_log_normalize(self, transformer):
        data = list(range(1, 11))
        result = transformer.transform(
            {"source": "test", "data": data},
            {"method": "log_normalize"},
        )
        transformed = result["transformed"]
        assert len(transformed) == 10
        assert abs(sum(transformed) / len(transformed)) < 0.01  # mean approx 0 after normalization

    def test_min_max(self, transformer):
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = transformer.transform(
            {"source": "test", "data": data},
            {"method": "min_max"},
        )
        assert result["transformed"][0] == 0.0
        assert result["transformed"][-1] == 1.0

    def test_extract_field(self, transformer):
        data = {"field1": {"nested": 42}, "field2": 100}
        result = transformer.transform(
            {"source": "test", "data": data},
            {"method": "extract_field", "params": {"field": "field1"}},
        )
        assert result["transformed"]["nested"] == 42

    def test_unknown_method(self, transformer):
        with pytest.raises(TransformationError, match="Unknown transformation"):
            transformer.transform(
                {"source": "test", "data": 1},
                {"method": "nonexistent"},
            )

    def test_quality_empty_list(self, transformer):
        result = transformer.transform(
            {"source": "test", "data": []},
            {"method": "identity"},
        )
        assert "empty_result" in result["quality_flags"]
        assert result["quality_score"] < 1.0

    def test_quality_null_values(self, transformer):
        data = [1, None, 3, None, 5]
        result = transformer.transform(
            {"source": "test", "data": data},
            {"method": "identity"},
        )
        assert "null_values" in result["quality_flags"]

    def test_csv_output_written(self, transformer):
        data = [1.0, 2.0, 3.0]
        result = transformer.transform(
            {"source": "test", "data": data},
            {"method": "identity", "experiment_id": "009"},
        )
        csv_path = os.path.join(transformer.transformed_dir, "009_test.csv")
        assert os.path.exists(csv_path)
        with open(csv_path) as f:
            content = f.read()
        assert "value" in content
        assert "1.0" in content

    def test_output_rows_count(self, transformer):
        data = [1, 2, 3, 4, 5]
        result = transformer.transform(
            {"source": "test", "data": data},
            {"method": "identity"},
        )
        assert result["output_rows"] == 5

    def test_double_log_normalize_maintains_order(self, transformer):
        data = [1, 10, 100, 1000]
        result = transformer.transform(
            {"source": "test", "data": data},
            {"method": "log_normalize"},
        )
        t = result["transformed"]
        for i in range(len(t) - 1):
            assert t[i] <= t[i + 1]  # monotonic increasing preserved
