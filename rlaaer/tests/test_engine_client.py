"""Tests for the Engine Client."""

import pytest
from unittest.mock import patch, MagicMock

from rlaaer.execution.engine_client import EngineClient


class TestEngineClient:
    @pytest.fixture
    def client(self):
        return EngineClient(base_url="http://localhost:9999")

    def test_ping_success(self, client):
        with patch.object(client, '_probe_socket', return_value=True):
            with patch("requests.Session.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response
                assert client.ping() is True

    def test_ping_failure(self, client):
        with patch("requests.Session.get") as mock_get:
            import requests
            mock_get.side_effect = requests.RequestException("Failed")
            assert client.ping() is False

    def test_start_simulation(self, client):
        with patch("requests.Session.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"simulation_id": "sim_001", "status": "running"}
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = client.start_simulation({"n_pillars": 16})
            assert result["simulation_id"] == "sim_001"

    def test_step(self, client):
        with patch("requests.Session.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"tick": 10, "entities": []}
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = client.step("sim_001", ticks=10)
            assert result["tick"] == 10

    def test_get_state(self, client):
        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"tick": 50, "entities": []}
            mock_get.return_value = mock_response

            result = client.get_state("sim_001")
            assert result["tick"] == 50

    def test_get_metrics(self, client):
        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"coherence": 0.85, "entropy": 1.2}
            mock_get.return_value = mock_response

            result = client.get_metrics("sim_001")
            assert result["coherence"] == 0.85

    def test_stop_simulation(self, client):
        with patch("requests.Session.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            assert client.stop_simulation("sim_001") is True

    def test_stop_simulation_failure(self, client):
        with patch("requests.Session.post") as mock_post:
            import requests
            mock_post.side_effect = requests.RequestException("Failed")
            assert client.stop_simulation("sim_001") is False

    def test_set_parameter(self, client):
        with patch("requests.Session.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"parameter": "coupling", "value": 0.5, "applied": True}
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = client.set_parameter("sim_001", "coupling", 0.5)
            assert result["applied"] is True

    def test_close(self, client):
        with patch("requests.Session.close") as mock_close:
            client.close()
            mock_close.assert_called_once()
