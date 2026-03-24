"""Load test for Compliance Advisor API endpoints.

Usage:
    pip install locust
    locust -f loadtest/locustfile.py --host https://cadvisor-func-prod.azurewebsites.net
"""

from locust import HttpUser, between, task


class DashboardUser(HttpUser):
    """Simulates a dashboard user browsing compliance data."""

    wait_time = between(1, 3)

    @task(10)
    def status(self):
        self.client.post("/api/advisor/status", json={})

    @task(8)
    def overview(self):
        self.client.post("/api/advisor/overview", json={})

    @task(5)
    def ediscovery(self):
        self.client.post("/api/advisor/ediscovery", json={})

    @task(5)
    def labels(self):
        self.client.post("/api/advisor/labels", json={})

    @task(5)
    def audit(self):
        self.client.post("/api/advisor/audit", json={})

    @task(5)
    def dlp(self):
        self.client.post("/api/advisor/dlp", json={})

    @task(5)
    def irm(self):
        self.client.post("/api/advisor/irm", json={})

    @task(3)
    def purview_incidents(self):
        self.client.post("/api/advisor/purview-incidents", json={})

    @task(3)
    def info_barriers(self):
        self.client.post("/api/advisor/info-barriers", json={})

    @task(5)
    def governance(self):
        self.client.post("/api/advisor/governance", json={})

    @task(5)
    def trend(self):
        self.client.post("/api/advisor/trend", json={"days": 30})

    @task(3)
    def actions(self):
        self.client.post("/api/advisor/actions", json={})

    @task(3)
    def dlp_policies(self):
        self.client.post("/api/advisor/dlp-policies", json={})

    @task(3)
    def irm_policies(self):
        self.client.post("/api/advisor/irm-policies", json={})

    @task(3)
    def assessments(self):
        self.client.post("/api/advisor/assessments", json={})

    @task(3)
    def threat_assessments(self):
        self.client.post("/api/advisor/threat-assessments", json={})

    @task(1)
    def briefing(self):
        self.client.post("/api/advisor/briefing", json={})

    @task(1)
    def ask(self):
        self.client.post(
            "/api/advisor/ask",
            json={"question": "What is our current compliance posture?"},
        )
