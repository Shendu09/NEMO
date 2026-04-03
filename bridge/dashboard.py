"""NEMO-OS Security Dashboard — Real-time monitoring and action approval interface."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from flask import Flask, render_template, jsonify, request
from core.security.audit_logger_v2 import AuditLogger
from core.security.action_classifier import RiskLevel

logger = logging.getLogger("nemo.dashboard")


class DashboardApp:
    """Dashboard application for NEMO-OS monitoring."""

    def __init__(self, audit_logger: Optional[AuditLogger] = None):
        """Initialize dashboard with audit logger reference."""
        self.app = Flask(
            __name__,
            template_folder=str(Path(__file__).parent / "templates"),
            static_folder=str(Path(__file__).parent / "static"),
        )
        self.audit_logger = audit_logger
        self._register_routes()

    def _register_routes(self) -> None:
        """Register all dashboard routes."""
        @self.app.route("/dashboard")
        def dashboard():
            """Serve main dashboard page."""
            return render_template("dashboard.html")

        @self.app.route("/api/audit-log")
        def api_audit_log():
            """Get audit log entries."""
            try:
                limit = request.args.get("limit", 50, type=int)
                risk_filter = request.args.get("risk", "", type=str)  # Filter by risk level

                if not self.audit_logger:
                    return jsonify({"entries": [], "total": 0}), 200

                # Read audit log from file
                log_path = self.audit_logger.log_path
                entries = []

                if log_path.exists():
                    with open(log_path, "r") as f:
                        lines = f.readlines()
                        # Parse JSONL format (newest last, so reverse)
                        for line in reversed(lines[-limit:]):
                            try:
                                entry = json.loads(line.strip())
                                # Apply risk filter if specified
                                if risk_filter and entry.get("risk_level") != risk_filter:
                                    continue
                                entries.append(entry)
                            except json.JSONDecodeError:
                                continue

                return jsonify({
                    "entries": entries,
                    "total": len(entries),
                    "limit": limit,
                }), 200

            except Exception as e:
                logger.error(f"Error fetching audit log: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/pending-actions")
        def api_pending_actions():
            """Get pending HIGH-risk actions awaiting approval."""
            try:
                # This will be called from the main nemo_server.py
                # For now, return empty - will be populated by endpoint calls
                pending = []
                return jsonify({
                    "actions": pending,
                    "count": len(pending),
                }), 200

            except Exception as e:
                logger.error(f"Error fetching pending actions: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/stats")
        def api_stats():
            """Get dashboard statistics."""
            try:
                if not self.audit_logger:
                    return jsonify({
                        "by_risk": {"LOW": 0, "MEDIUM": 0, "HIGH": 0},
                        "by_action": {},
                        "success_rate": 0,
                        "total_actions": 0,
                    }), 200

                log_path = self.audit_logger.log_path
                stats = {
                    "by_risk": {"LOW": 0, "MEDIUM": 0, "HIGH": 0},
                    "by_action": {},
                    "success_rate": 0,
                    "total_actions": 0,
                    "successes": 0,
                }

                if log_path.exists():
                    with open(log_path, "r") as f:
                        for line in f:
                            try:
                                entry = json.loads(line.strip())

                                # Count by risk level
                                risk = entry.get("risk_level", "UNKNOWN")
                                if risk in ["LOW", "MEDIUM", "HIGH"]:
                                    stats["by_risk"][risk] += 1

                                # Count by action
                                action = entry.get("action", "unknown")
                                stats["by_action"][action] = stats["by_action"].get(action, 0) + 1

                                # Count successes
                                stats["total_actions"] += 1
                                if entry.get("allowed", False):
                                    stats["successes"] += 1

                            except json.JSONDecodeError:
                                continue

                # Calculate success rate
                if stats["total_actions"] > 0:
                    stats["success_rate"] = int(
                        (stats["successes"] / stats["total_actions"]) * 100
                    )

                return jsonify(stats), 200

            except Exception as e:
                logger.error(f"Error calculating stats: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/health")
        def api_health():
            """Get NEMO health status."""
            return jsonify({
                "status": "ok",
                "security": "active",
                "timestamp": datetime.now().isoformat(),
            }), 200


def create_dashboard_app(audit_logger: Optional[AuditLogger] = None) -> Flask:
    """Factory function to create dashboard Flask app."""
    dashboard = DashboardApp(audit_logger)
    return dashboard.app
