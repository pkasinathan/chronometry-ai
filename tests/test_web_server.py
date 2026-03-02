"""Tests for web_server.py module - Web dashboard and API endpoints."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest
import yaml

from chronometry.web_server import app, init_config


class TestConfiguration:
    """Tests for web server configuration."""

    @patch("chronometry.web_server.load_config")
    @patch("chronometry.web_server.ensure_absolute_path")
    def test_init_config_success(self, mock_ensure, mock_load):
        """Test successful configuration initialization."""
        mock_load.return_value = {
            "root_dir": "./data",
            "server": {"secret_key": "test-secret", "host": "0.0.0.0", "port": 8051},
        }
        mock_ensure.return_value = "/absolute/path/data"

        init_config()

        assert app.config["SECRET_KEY"] == "test-secret"

    @patch("chronometry.web_server.load_config")
    def test_init_config_uses_defaults(self, mock_load):
        """Test that defaults are used when not in config."""
        mock_load.return_value = {
            "root_dir": "./data",
            "server": {},  # Empty server config
        }

        init_config()

        # Should use default secret key
        assert app.config["SECRET_KEY"] == "change-me-in-production"

    @patch("chronometry.web_server.load_config")
    def test_init_config_handles_error(self, mock_load):
        """Test configuration error handling."""
        mock_load.side_effect = Exception("Config failed")

        with pytest.raises(Exception):
            init_config()


class TestDataEndpoints:
    """Tests for data API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def setup_config(self):
        """Setup configuration for tests."""
        with patch(
            "chronometry.web_server.config",
            {
                "root_dir": "/tmp/test",
                "capture": {"capture_interval_seconds": 900, "monitor_index": 1, "retention_days": 30},
                "annotation": {"batch_size": 4, "prompt": "Test"},
                "timeline": {"bucket_minutes": 15},
                "digest": {"interval_seconds": 3600},
            },
        ):
            yield

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert "timestamp" in data
        from chronometry import __version__

        assert data["version"] == __version__

    def test_get_config(self, client, setup_config):
        """Test get configuration endpoint."""
        response = client.get("/api/config")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "capture" in data
        assert "annotation" in data
        assert "timeline" in data
        assert "local_model" in data["annotation"]
        assert "local_model" in data["digest"]

    @patch("chronometry.web_server.load_annotations")
    @patch("chronometry.web_server.group_activities")
    @patch("chronometry.web_server.calculate_stats")
    def test_get_stats(self, mock_stats, mock_group, mock_load, client, tmp_path):
        """Test stats endpoint."""
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        date_dir = frames_dir / "2025-11-01"
        date_dir.mkdir()
        (date_dir / "20251101_100000.json").write_text("{}")

        mock_load.return_value = [{"datetime": datetime(2025, 11, 1, 10, 0), "summary": "Test"}]
        mock_group.return_value = [{"category": "Code"}]
        mock_stats.return_value = {"focus_percentage": 80, "distraction_percentage": 20}

        with patch("chronometry.web_server.config", {"root_dir": str(tmp_path)}):
            response = client.get("/api/stats")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "total_days" in data
        assert "total_frames" in data

    @patch("chronometry.web_server.load_annotations")
    @patch("chronometry.web_server.group_activities")
    @patch("chronometry.web_server.get_daily_dir")
    def test_get_timeline_by_date(self, mock_daily_dir, mock_group, mock_load, client, setup_config, tmp_path):
        """Test timeline by date endpoint."""
        daily_dir = tmp_path / "2025-11-01"
        daily_dir.mkdir()
        mock_daily_dir.return_value = daily_dir

        mock_load.return_value = [{"datetime": datetime(2025, 11, 1, 10, 0), "summary": "Test"}]
        mock_group.return_value = [
            {
                "category": "Code",
                "icon": "💻",
                "color": "#E50914",
                "start_time": datetime(2025, 11, 1, 10, 0),
                "end_time": datetime(2025, 11, 1, 10, 30),
                "summary": "Coding",
                "frames": [],
            }
        ]

        with patch("chronometry.web_server.calculate_stats") as mock_stats:
            mock_stats.return_value = {"focus_percentage": 100}

            response = client.get("/api/timeline/2025-11-01")

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["date"] == "2025-11-01"
            assert len(data["activities"]) == 1

    @patch("chronometry.web_server.get_or_generate_digest")
    def test_get_digest(self, mock_digest, client, setup_config):
        """Test digest endpoint."""
        mock_digest.return_value = {"date": "2025-11-01", "overall_summary": "Test summary", "category_summaries": {}}

        response = client.get("/api/digest")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["overall_summary"] == "Test summary"

    @patch("chronometry.web_server.get_or_generate_digest")
    def test_get_digest_force_regenerate(self, mock_digest, client, setup_config):
        """Test digest force regenerate parameter."""
        mock_digest.return_value = {"date": "2025-11-01", "overall_summary": "New summary"}

        response = client.get("/api/digest?force=true")

        assert response.status_code == 200
        # Verify force_regenerate was passed
        assert mock_digest.call_args[1]["force_regenerate"] is True

    @patch("chronometry.web_server.load_annotations")
    @patch("chronometry.web_server.group_activities")
    @patch("chronometry.web_server.get_daily_dir")
    def test_search_activities(self, mock_daily_dir, mock_group, mock_load, client, tmp_path):
        """Test search endpoint."""
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        daily_dir = frames_dir / "2025-11-01"
        daily_dir.mkdir()
        mock_daily_dir.return_value = daily_dir

        mock_load.return_value = [{"datetime": datetime(2025, 11, 1, 10, 0), "summary": "Python coding"}]
        mock_group.return_value = [
            {
                "category": "Code",
                "icon": "💻",
                "color": "#E50914",
                "start_time": datetime(2025, 11, 1, 10, 0),
                "end_time": datetime(2025, 11, 1, 10, 30),
                "summary": "Python coding",
            }
        ]

        with patch("chronometry.web_server.config", {"root_dir": str(tmp_path)}):
            response = client.get("/api/search?q=python&days=1")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["count"] == 1
        assert data["results"][0]["summary"] == "Python coding"

    @patch("chronometry.web_server.TokenUsageTracker")
    @patch("chronometry.web_server.load_annotations")
    @patch("chronometry.web_server.group_activities")
    @patch("chronometry.web_server.calculate_stats")
    @patch("chronometry.web_server.get_daily_dir")
    def test_get_analytics(
        self, mock_daily_dir, mock_stats, mock_group, mock_load, mock_tracker_class, client, tmp_path
    ):
        """Test analytics endpoint."""
        daily_dir = tmp_path / "2025-11-01"
        daily_dir.mkdir()
        mock_daily_dir.return_value = daily_dir

        mock_load.return_value = [{"datetime": datetime(2025, 11, 1, 10, 0), "summary": "Test"}]
        mock_group.return_value = [
            {"category": "Code", "start_time": datetime(2025, 11, 1, 10, 0), "end_time": datetime(2025, 11, 1, 10, 30)}
        ]
        mock_stats.return_value = {
            "focus_percentage": 80,
            "distraction_percentage": 20,
            "total_time": 30,
            "total_activities": 1,
            "focus_time": 24,
            "distraction_time": 6,
            "category_breakdown": {"Code": 30},
        }

        mock_tracker = Mock()
        mock_tracker.get_daily_usage.return_value = {"total_tokens": 100, "by_type": {"digest": 100}}
        mock_tracker_class.return_value = mock_tracker

        with patch("chronometry.web_server.config", {"root_dir": str(tmp_path)}):
            response = client.get("/api/analytics?days=1")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "daily_stats" in data
        assert "category_breakdown" in data
        assert "hourly_breakdown" in data
        assert "token_usage" in data


class TestExportEndpoints:
    """Tests for export endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def setup_config(self):
        """Setup configuration for tests."""
        with patch("chronometry.web_server.config", {"root_dir": "/tmp/test", "timeline": {"gap_minutes": 5}}):
            yield

    @patch("chronometry.web_server.load_annotations")
    @patch("chronometry.web_server.group_activities")
    @patch("chronometry.web_server.get_daily_dir")
    def test_export_csv(self, mock_daily_dir, mock_group, mock_load, client, setup_config, tmp_path):
        """Test CSV export endpoint."""
        daily_dir = tmp_path / "2025-11-01"
        daily_dir.mkdir()
        mock_daily_dir.return_value = daily_dir

        mock_load.return_value = [{"datetime": datetime(2025, 11, 1, 10, 0), "summary": "Test"}]
        mock_group.return_value = [
            {
                "category": "Code",
                "start_time": datetime(2025, 11, 1, 10, 0),
                "end_time": datetime(2025, 11, 1, 10, 30),
                "summary": "Coding",
            }
        ]

        response = client.get("/api/export/csv?date=2025-11-01")

        assert response.status_code == 200
        assert response.mimetype == "text/csv"
        assert b"Category" in response.data
        assert b"Code" in response.data

    @patch("chronometry.web_server.load_annotations")
    @patch("chronometry.web_server.group_activities")
    @patch("chronometry.web_server.calculate_stats")
    @patch("chronometry.web_server.get_daily_dir")
    def test_export_json(self, mock_daily_dir, mock_stats, mock_group, mock_load, client, setup_config, tmp_path):
        """Test JSON export endpoint."""
        daily_dir = tmp_path / "2025-11-01"
        daily_dir.mkdir()
        mock_daily_dir.return_value = daily_dir

        mock_load.return_value = [{"datetime": datetime(2025, 11, 1, 10, 0), "summary": "Test"}]
        mock_group.return_value = [
            {
                "category": "Code",
                "start_time": datetime(2025, 11, 1, 10, 0),
                "end_time": datetime(2025, 11, 1, 10, 30),
                "summary": "Coding",
            }
        ]
        mock_stats.return_value = {"focus_percentage": 100}

        response = client.get("/api/export/json?date=2025-11-01")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["date"] == "2025-11-01"
        assert len(data["activities"]) == 1

    @patch("chronometry.web_server.get_daily_dir")
    def test_export_csv_no_data(self, mock_daily_dir, client, setup_config, tmp_path):
        """Test CSV export with no data."""
        mock_daily_dir.return_value = tmp_path / "nonexistent"

        response = client.get("/api/export/csv?date=2025-11-01")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data

    @patch("chronometry.web_server.get_daily_dir")
    def test_export_json_no_data(self, mock_daily_dir, client, setup_config, tmp_path):
        """Test JSON export with no data."""
        mock_daily_dir.return_value = tmp_path / "nonexistent"

        response = client.get("/api/export/json?date=2025-11-01")

        assert response.status_code == 404


class TestFrameEndpoints:
    """Tests for frame-related endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def setup_config(self):
        """Setup configuration for tests."""
        with patch("chronometry.web_server.config", {"root_dir": "/tmp/test"}):
            yield

    @patch("chronometry.web_server.load_json")
    @patch("chronometry.web_server.get_daily_dir")
    def test_get_frames(self, mock_daily_dir, mock_load_json, client, setup_config, tmp_path):
        """Test get frames endpoint."""
        daily_dir = tmp_path / "2025-11-01"
        daily_dir.mkdir()
        mock_daily_dir.return_value = daily_dir

        # Create test JSON files
        json_file = daily_dir / "20251101_100000.json"
        json_file.write_text(json.dumps({"summary": "Test activity", "image_file": "20251101_100000.png"}))

        mock_load_json.return_value = {"summary": "Test activity", "image_file": "20251101_100000.png"}

        response = client.get("/api/frames?date=2025-11-01")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["frames"]) == 1
        assert data["frames"][0]["summary"] == "Test activity"

    @patch("chronometry.web_server.ensure_absolute_path")
    @patch("chronometry.web_server.get_daily_dir")
    def test_get_frame_image(self, mock_daily_dir, mock_ensure, client, tmp_path):
        """Test get frame image endpoint."""
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)
        image_path = daily_dir / "20251101_100000.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        mock_daily_dir.return_value = daily_dir
        mock_ensure.return_value = str(tmp_path)

        with patch("chronometry.web_server.config", {"root_dir": str(tmp_path)}):
            response = client.get("/api/frames/2025-11-01/20251101_100000/image")

        assert response.status_code == 200

    @patch("chronometry.web_server.get_daily_dir")
    @patch("chronometry.web_server.ensure_absolute_path")
    def test_get_frame_image_not_found(self, mock_ensure, mock_daily_dir, client, setup_config, tmp_path):
        """Test frame image endpoint with missing image."""
        mock_ensure.return_value = str(tmp_path)
        mock_daily_dir.return_value = tmp_path / "2025-11-01"

        response = client.get("/api/frames/2025-11-01/20251101_100000/image")

        assert response.status_code == 404


class TestDatesEndpoint:
    """Tests for available dates endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def setup_config(self):
        """Setup configuration for tests."""
        with patch("chronometry.web_server.config", {"root_dir": "/tmp/test"}):
            yield

    def test_get_available_dates(self, client, tmp_path):
        """Test get available dates endpoint."""
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()

        date_dir_1 = frames_dir / "2025-11-01"
        date_dir_1.mkdir()
        (date_dir_1 / "20251101_100000.json").write_text("{}")

        date_dir_2 = frames_dir / "2025-11-02"
        date_dir_2.mkdir()
        (date_dir_2 / "20251102_100000.json").write_text("{}")

        with (
            patch("chronometry.web_server.config", {"root_dir": str(tmp_path)}),
            patch("chronometry.web_server.parse_date") as mock_parse,
        ):
            mock_parse.side_effect = lambda d: datetime.strptime(d, "%Y-%m-%d")
            response = client.get("/api/dates")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "dates" in data
        assert len(data["dates"]) == 2


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def setup_config(self):
        """Setup configuration for tests."""
        with patch("chronometry.web_server.config", {"root_dir": "/tmp/test"}):
            yield

    def test_invalid_date_format(self, client, setup_config):
        """Test handling of invalid date format."""
        response = client.get("/api/timeline/invalid-date")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    @patch("chronometry.web_server.get_daily_dir")
    def test_timeline_no_directory(self, mock_daily_dir, client, setup_config, tmp_path):
        """Test timeline endpoint with missing directory."""
        mock_daily_dir.return_value = tmp_path / "nonexistent"

        response = client.get("/api/timeline/2025-11-01")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["activities"] == []

    @patch("chronometry.web_server.get_daily_dir")
    def test_frames_no_directory(self, mock_daily_dir, client, setup_config, tmp_path):
        """Test frames endpoint with missing directory."""
        mock_daily_dir.return_value = tmp_path / "nonexistent"

        response = client.get("/api/frames?date=2025-11-01")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["frames"] == []


class TestConfigurationUpdate:
    """Tests for configuration update endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @patch("chronometry.web_server.backup_config")
    @patch("chronometry.web_server.init_config")
    def test_update_config_user_config(self, mock_init, mock_backup, client, tmp_path):
        """Test updating user configuration."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "user_config.yaml"
        config_file.write_text("capture:\n  capture_interval_seconds: 900\n")

        with patch("chronometry.web_server.CHRONOMETRY_HOME", tmp_path):
            response = client.put(
                "/api/config",
                data=json.dumps({"capture": {"capture_interval_seconds": 600}}),
                content_type="application/json",
            )

            assert response.status_code == 200
            updated = yaml.safe_load(config_file.read_text())
            assert updated["capture"]["capture_interval_seconds"] == 600
            mock_backup.assert_called_once_with(config_file)
            mock_init.assert_called_once()

    @patch("chronometry.web_server.backup_config")
    @patch("chronometry.web_server.init_config")
    def test_update_config_deep_merges_local_model(self, mock_init, mock_backup, client, tmp_path):
        """Test nested local_model updates preserve existing sibling keys."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "user_config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "annotation": {
                        "local_model": {
                            "provider": "ollama",
                            "model_name": "qwen3-vl:8b",
                            "fallback_model_name": "qwen2.5vl:7b",
                            "timeout_sec": 300,
                            "max_retries": 3,
                            "keep_alive": "1m",
                        }
                    },
                    "digest": {"local_model": {"provider": "ollama", "model_name": "qwen3-vl:8b", "timeout_sec": 300}},
                },
                sort_keys=False,
            )
        )

        payload = {
            "annotation": {"local_model": {"keep_alive": "0", "timeout_sec": 120}},
            "digest": {"local_model": {"keep_alive": "10m"}},
        }

        with patch("chronometry.web_server.CHRONOMETRY_HOME", tmp_path):
            response = client.put(
                "/api/config",
                data=json.dumps(payload),
                content_type="application/json",
            )

        assert response.status_code == 200
        updated = yaml.safe_load(config_file.read_text())
        assert updated["annotation"]["local_model"]["keep_alive"] == "0"
        assert updated["annotation"]["local_model"]["timeout_sec"] == 120
        assert updated["annotation"]["local_model"]["model_name"] == "qwen3-vl:8b"
        assert updated["annotation"]["local_model"]["fallback_model_name"] == "qwen2.5vl:7b"
        assert updated["digest"]["local_model"]["keep_alive"] == "10m"
        assert updated["digest"]["local_model"]["model_name"] == "qwen3-vl:8b"
        mock_backup.assert_called_once_with(config_file)
        mock_init.assert_called_once()


class TestWebSocketEvents:
    """Tests for WebSocket event handlers."""

    def test_handle_connect(self):
        """Test WebSocket connect handler."""
        from chronometry.web_server import handle_connect

        with patch("chronometry.web_server.emit") as mock_emit:
            handle_connect()

            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][0] == "connected"

    def test_handle_disconnect(self):
        """Test WebSocket disconnect handler."""
        from chronometry.web_server import handle_disconnect

        # Should not raise exception
        handle_disconnect()

    def test_handle_subscribe_live(self):
        """Test WebSocket subscribe handler."""
        from chronometry.web_server import handle_subscribe_live

        with patch("chronometry.web_server.emit") as mock_emit:
            handle_subscribe_live()

            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][0] == "subscribed"

    def test_broadcast_new_frame(self):
        """Test broadcasting new frame event."""
        from chronometry.web_server import broadcast_new_frame

        with patch("chronometry.web_server.socketio.emit") as mock_emit:
            frame_data = {"timestamp": "20251101_100000"}
            broadcast_new_frame(frame_data)

            mock_emit.assert_called_once_with("new_frame", frame_data)

    def test_broadcast_new_activity(self):
        """Test broadcasting new activity event."""
        from chronometry.web_server import broadcast_new_activity

        with patch("chronometry.web_server.socketio.emit") as mock_emit:
            activity_data = {"category": "Code"}
            broadcast_new_activity(activity_data)

            mock_emit.assert_called_once_with("new_activity", activity_data)


class TestConfigReset:
    """Tests for POST /api/config/reset endpoint."""

    @patch("chronometry.web_server.init_config")
    @patch("chronometry.web_server.bootstrap")
    def test_reset_config_calls_bootstrap_force(self, mock_bootstrap, mock_init):
        """Test that reset endpoint calls bootstrap(force=True)."""
        with app.test_client() as client:
            response = client.post("/api/config/reset")

        assert response.status_code == 200
        mock_bootstrap.assert_called_once_with(force=True)
        mock_init.assert_called_once()
        data = response.get_json()
        assert data["status"] == "success"

    @patch("chronometry.web_server.init_config")
    @patch("chronometry.web_server.bootstrap", side_effect=Exception("bootstrap failed"))
    def test_reset_config_handles_error(self, mock_bootstrap, mock_init):
        """Test that reset endpoint handles errors gracefully."""
        with app.test_client() as client:
            response = client.post("/api/config/reset")

        assert response.status_code == 500
        data = response.get_json()
        assert data["status"] == "error"


class TestConfigUpdateValidation:
    """Tests for PUT /api/config input validation."""

    def test_update_config_rejects_null_body(self):
        """Test that non-dict JSON body returns 400."""
        with app.test_client() as client:
            response = client.put(
                "/api/config",
                json=[1, 2, 3],
            )
        assert response.status_code == 400
        data = response.get_json()
        assert "JSON object" in data["message"]

    @patch("chronometry.web_server.backup_config")
    def test_update_config_rejects_non_dict_section(self, mock_backup, tmp_path, monkeypatch):
        """Test that non-dict section values return 400."""
        import chronometry.web_server as ws

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        user_config = config_dir / "user_config.yaml"
        user_config.write_text("# empty\n")
        monkeypatch.setattr(ws, "CHRONOMETRY_HOME", tmp_path)

        with app.test_client() as client:
            response = client.put(
                "/api/config",
                json={"capture": "not a dict"},
            )
        assert response.status_code == 400
        data = response.get_json()
        assert "'capture' must be a JSON object" in data["message"]


class TestSystemHealthEndpoint:
    """Tests for /api/system-health endpoint."""

    def test_system_health_snapshot_shape(self):
        expected = {
            "server_start_time": "2026-03-02T10:00:00",
            "uptime_seconds": 42,
            "capture": {"attempted": 1, "succeeded": 1, "skipped_locked": 0, "skipped_camera": 0, "failed": 0},
            "annotation": {"runs": 1, "frames_attempted": 1, "frames_succeeded": 1, "frames_failed": 0},
            "llm": {
                "vision_calls": 1,
                "vision_succeeded": 1,
                "vision_failed": 0,
                "text_calls": 1,
                "text_succeeded": 1,
                "text_failed": 0,
                "text_empty_content": 0,
            },
            "digest": {"generated": 1, "failed": 0, "cached_hits": 0},
        }

        with patch("chronometry.runtime_stats.stats.snapshot", return_value=expected):
            with app.test_client() as client:
                response = client.get("/api/system-health")

        assert response.status_code == 200
        assert response.get_json() == expected

    def test_system_health_handles_error(self):
        with patch("chronometry.runtime_stats.stats.snapshot", side_effect=Exception("boom")):
            with app.test_client() as client:
                response = client.get("/api/system-health")

        assert response.status_code == 500
        data = response.get_json()
        assert data["error"] == "Failed to load system health"


class TestSecretKeyWarning:
    """Tests for secret key warning at startup."""

    @patch("chronometry.web_server.load_config")
    @patch("chronometry.web_server.ensure_absolute_path")
    @patch("chronometry.web_server.logger")
    def test_warns_on_default_secret_key(self, mock_logger, mock_ensure, mock_load):
        """Test that a warning is logged when SECRET_KEY is the insecure default."""
        mock_load.return_value = {
            "root_dir": "./data",
            "server": {"secret_key": "change-me-in-production"},
        }
        mock_ensure.return_value = "/abs/data"

        init_config()

        mock_logger.warning.assert_any_call(
            "SECRET_KEY is the insecure default! Run 'chrono init' or set server.secret_key in user_config.yaml."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
