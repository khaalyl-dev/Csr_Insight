import unittest
from types import SimpleNamespace
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from flask import Flask, request

from features.csr_plan_management import csr_plans_routes as routes


class CsrPlanCrudUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)

    @contextmanager
    def _ctx(self, method: str, path: str, *, json=None, role="SITE_USER", user_id="u-1", args=None):
        query_string = args or {}
        with self.app.test_request_context(path, method=method, json=json, query_string=query_string):
            request.role = role
            request.user_id = user_id
            yield

    # ---------- CREATE ----------
    @patch("features.csr_plan_management.csr_plans_routes._plan_to_json", return_value={"id": "p-1"})
    @patch("features.csr_plan_management.csr_plans_routes.snapshot_plan", return_value={"id": "snap"})
    @patch("features.csr_plan_management.csr_plans_routes.audit_create")
    def test_create_plan_corporate_success(self, _audit, _snap, _to_json):
        class FakePlan:
            query = MagicMock()

            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
                self.id = "p-1"

        FakePlan.query.filter_by.return_value.first.return_value = None

        with patch("features.csr_plan_management.csr_plans_routes.CsrPlan", FakePlan), patch.object(
            routes.db.session, "add"
        ) as mock_add, patch.object(routes.db.session, "flush"), patch.object(routes.db.session, "commit"), patch(
            "features.csr_plan_management.csr_plans_routes._user_can_access_site"
        ) as mock_access:
            with self._ctx("POST", "/api/csr-plans", json={"site_id": "s-1", "year": 2026}, role="CORPORATE_USER"):
                response, status = routes.create_plan.__wrapped__()

        self.assertEqual(status, 201)
        self.assertEqual(response.get_json()["id"], "p-1")
        created = mock_add.call_args[0][0]
        self.assertEqual(created.site_id, "s-1")
        self.assertEqual(created.year, 2026)
        mock_access.assert_not_called()

    @patch("features.csr_plan_management.csr_plans_routes._user_can_access_site", return_value=False)
    def test_create_plan_site_level0_forbidden_without_access(self, _access):
        with self._ctx(
            "POST",
            "/api/csr-plans",
            json={"site_id": "s-1", "year": 2026},
            role="SITE_USER",
            user_id="site-l0",
        ):
            response, status = routes.create_plan.__wrapped__()
        self.assertEqual(status, 403)

    @patch("features.csr_plan_management.csr_plans_routes._plan_to_json", return_value={"id": "p-2"})
    @patch("features.csr_plan_management.csr_plans_routes.snapshot_plan", return_value={"id": "snap"})
    @patch("features.csr_plan_management.csr_plans_routes.audit_create")
    @patch("features.csr_plan_management.csr_plans_routes._user_can_access_site", return_value=True)
    def test_create_plan_site_level1_success(self, _access, _audit, _snap, _to_json):
        class FakePlan:
            query = MagicMock()

            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
                self.id = "p-2"

        FakePlan.query.filter_by.return_value.first.return_value = None
        with patch("features.csr_plan_management.csr_plans_routes.CsrPlan", FakePlan), patch.object(
            routes.db.session, "add"
        ), patch.object(routes.db.session, "flush"), patch.object(routes.db.session, "commit"):
            with self._ctx(
                "POST",
                "/api/csr-plans",
                json={"site_id": "s-1", "year": "2027", "validation_mode": "111"},
                role="SITE_USER",
                user_id="site-l1",
            ):
                response, status = routes.create_plan.__wrapped__()
        self.assertEqual(status, 201)
        self.assertEqual(response.get_json()["id"], "p-2")

    # ---------- READ/LIST ----------
    @patch("features.csr_plan_management.csr_plans_routes._plan_to_json", return_value={"id": "p-1", "status": "DRAFT"})
    def test_list_plans_corporate_returns_data(self, _to_json):
        fake_plan = SimpleNamespace(id="p-1", status="DRAFT")
        fake_query = MagicMock()
        fake_query.order_by.return_value.all.return_value = [fake_plan]

        fake_plan_model = SimpleNamespace(query=fake_query, year=SimpleNamespace(desc=lambda: None), created_at=SimpleNamespace(desc=lambda: None), site_id=SimpleNamespace(in_=lambda _x: None))
        fake_activity_model = SimpleNamespace(query=MagicMock())
        fake_activity_model.query.filter_by.return_value.count.return_value = 3

        with patch("features.csr_plan_management.csr_plans_routes.CsrPlan", fake_plan_model), patch(
            "models.CsrActivity", fake_activity_model
        ):
            with self._ctx("GET", "/api/csr-plans", role="CORPORATE_USER", user_id="corp"):
                response, status = routes.list_plans.__wrapped__()

        self.assertEqual(status, 200)
        payload = response.get_json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["activities_count"], 3)

    def test_list_plans_site_level0_no_sites_returns_empty(self):
        fake_query = MagicMock()
        fake_plan_model = SimpleNamespace(query=fake_query, site_id=SimpleNamespace(in_=lambda _x: None))
        fake_usersite_model = SimpleNamespace(query=MagicMock())
        fake_usersite_model.query.filter_by.return_value.all.return_value = []

        with patch("features.csr_plan_management.csr_plans_routes.CsrPlan", fake_plan_model), patch(
            "features.csr_plan_management.csr_plans_routes.UserSite", fake_usersite_model
        ):
            with self._ctx("GET", "/api/csr-plans", role="SITE_USER", user_id="site-l0"):
                response, status = routes.list_plans.__wrapped__()

        self.assertEqual(status, 200)
        self.assertEqual(response.get_json(), [])

    @patch("features.csr_plan_management.csr_plans_routes._plan_to_json", return_value={"id": "p-3", "status": "SUBMITTED"})
    @patch("features.csr_plan_management.csr_plans_routes._compute_can_approve", return_value=True)
    def test_list_plans_site_level1_with_site_access(self, _can_approve, _to_json):
        fake_plan = SimpleNamespace(id="p-3", status="SUBMITTED")
        fake_query = MagicMock()
        fake_query.filter.return_value = fake_query
        fake_query.order_by.return_value.all.return_value = [fake_plan]
        fake_plan_model = SimpleNamespace(
            query=fake_query,
            site_id=SimpleNamespace(in_=lambda _x: None),
            year=SimpleNamespace(desc=lambda: None),
            created_at=SimpleNamespace(desc=lambda: None),
        )

        fake_usersite_model = SimpleNamespace(query=MagicMock())
        fake_usersite_model.query.filter_by.return_value.all.return_value = [SimpleNamespace(site_id="s-1", grade="level_1")]
        fake_activity_model = SimpleNamespace(query=MagicMock())
        fake_activity_model.query.filter_by.return_value.count.return_value = 1

        with patch("features.csr_plan_management.csr_plans_routes.CsrPlan", fake_plan_model), patch(
            "features.csr_plan_management.csr_plans_routes.UserSite", fake_usersite_model
        ), patch("models.CsrActivity", fake_activity_model):
            with self._ctx("GET", "/api/csr-plans", role="SITE_USER", user_id="site-l1"):
                response, status = routes.list_plans.__wrapped__()

        self.assertEqual(status, 200)
        payload = response.get_json()
        self.assertEqual(len(payload), 1)
        self.assertTrue(payload[0]["can_approve"])

    # ---------- UPDATE ----------
    @patch("features.csr_plan_management.csr_plans_routes._plan_to_json", return_value={"id": "p-upd"})
    @patch("features.csr_plan_management.csr_plans_routes.snapshot_plan", return_value={"id": "snap"})
    @patch("features.csr_plan_management.csr_plans_routes.audit_update")
    @patch("features.csr_plan_management.csr_plans_routes._plan_is_editable", return_value=True)
    def test_update_plan_corporate_success(self, _editable, _audit, _snapshot, _to_json):
        plan = SimpleNamespace(id="p-upd", site_id="s-1", year=2026, status="DRAFT", allocated_budget=None, validation_mode="101")
        fake_plan_model = SimpleNamespace(query=MagicMock())
        fake_plan_model.query.get.return_value = plan
        fake_plan_model.query.filter_by.return_value.first.return_value = None

        with patch("features.csr_plan_management.csr_plans_routes.CsrPlan", fake_plan_model), patch.object(
            routes.db.session, "commit"
        ):
            with self._ctx(
                "PATCH",
                "/api/csr-plans/p-upd",
                json={"year": 2028, "allocated_budget": 1500, "validation_mode": "111"},
                role="CORPORATE_USER",
                user_id="corp",
            ):
                response, status = routes.update_plan.__wrapped__("p-upd")

        self.assertEqual(status, 200)
        self.assertEqual(plan.year, 2028)
        self.assertEqual(plan.allocated_budget, 1500)
        self.assertEqual(plan.validation_mode, "111")
        self.assertEqual(response.get_json()["id"], "p-upd")

    @patch("features.csr_plan_management.csr_plans_routes._plan_is_editable", return_value=True)
    @patch("features.csr_plan_management.csr_plans_routes._user_can_access_site", return_value=False)
    def test_update_plan_site_level0_forbidden(self, _access, _editable):
        plan = SimpleNamespace(id="p-upd", site_id="s-1", year=2026, status="DRAFT")
        fake_plan_model = SimpleNamespace(query=MagicMock())
        fake_plan_model.query.get.return_value = plan

        with patch("features.csr_plan_management.csr_plans_routes.CsrPlan", fake_plan_model):
            with self._ctx("PATCH", "/api/csr-plans/p-upd", json={"year": 2028}, role="SITE_USER", user_id="site-l0"):
                response, status = routes.update_plan.__wrapped__("p-upd")
        self.assertEqual(status, 403)

    @patch("features.csr_plan_management.csr_plans_routes._plan_to_json", return_value={"id": "p-upd-ok"})
    @patch("features.csr_plan_management.csr_plans_routes.snapshot_plan", return_value={"id": "snap"})
    @patch("features.csr_plan_management.csr_plans_routes.audit_update")
    @patch("features.csr_plan_management.csr_plans_routes._plan_is_editable", return_value=True)
    @patch("features.csr_plan_management.csr_plans_routes._user_can_access_site", return_value=True)
    def test_update_plan_site_level1_success(self, _access, _editable, _audit, _snapshot, _to_json):
        plan = SimpleNamespace(id="p-upd-ok", site_id="s-1", year=2026, status="DRAFT", allocated_budget=None, validation_mode="101")
        fake_plan_model = SimpleNamespace(query=MagicMock())
        fake_plan_model.query.get.return_value = plan
        fake_plan_model.query.filter_by.return_value.first.return_value = None

        with patch("features.csr_plan_management.csr_plans_routes.CsrPlan", fake_plan_model), patch.object(
            routes.db.session, "commit"
        ):
            with self._ctx(
                "PATCH",
                "/api/csr-plans/p-upd-ok",
                json={"allocated_budget": "700"},
                role="SITE_USER",
                user_id="site-l1",
            ):
                response, status = routes.update_plan.__wrapped__("p-upd-ok")
        self.assertEqual(status, 200)
        self.assertEqual(plan.allocated_budget, 700.0)
        self.assertEqual(response.get_json()["id"], "p-upd-ok")

    # ---------- DELETE ----------
    @patch("features.csr_plan_management.csr_plans_routes.snapshot_plan", return_value={"id": "snap"})
    @patch("features.csr_plan_management.csr_plans_routes.audit_delete")
    @patch("features.csr_plan_management.csr_plans_routes._plan_is_editable", return_value=True)
    def test_delete_plan_corporate_success(self, _editable, _audit, _snapshot):
        plan = SimpleNamespace(id="p-del", site_id="s-1", year=2026, status="DRAFT")
        fake_plan_model = SimpleNamespace(query=MagicMock())
        fake_plan_model.query.get.return_value = plan
        fake_activity_model = object()

        with patch("features.csr_plan_management.csr_plans_routes.CsrPlan", fake_plan_model), patch(
            "models.CsrActivity", fake_activity_model
        ), patch.object(routes.db.session, "query") as mock_q, patch.object(routes.db.session, "delete") as mock_delete, patch.object(
            routes.db.session, "commit"
        ), patch(
            "features.csr_plan_management.csr_plans_routes._user_can_access_site"
        ) as mock_access:
            mock_q.return_value.filter_by.return_value.delete.return_value = None
            with self._ctx("DELETE", "/api/csr-plans/p-del", role="CORPORATE_USER", user_id="corp"):
                response, status = routes.delete_plan.__wrapped__("p-del")

        self.assertEqual(status, 200)
        self.assertIn("supprim", response.get_json()["message"].lower())
        mock_delete.assert_called_once_with(plan)
        mock_access.assert_not_called()

    @patch("features.csr_plan_management.csr_plans_routes._plan_is_editable", return_value=True)
    @patch("features.csr_plan_management.csr_plans_routes._user_can_access_site", return_value=False)
    def test_delete_plan_site_level0_forbidden(self, _access, _editable):
        plan = SimpleNamespace(id="p-del-no", site_id="s-1", year=2026, status="DRAFT")
        fake_plan_model = SimpleNamespace(query=MagicMock())
        fake_plan_model.query.get.return_value = plan
        with patch("features.csr_plan_management.csr_plans_routes.CsrPlan", fake_plan_model):
            with self._ctx("DELETE", "/api/csr-plans/p-del-no", role="SITE_USER", user_id="site-l0"):
                response, status = routes.delete_plan.__wrapped__("p-del-no")
        self.assertEqual(status, 403)

    @patch("features.csr_plan_management.csr_plans_routes.snapshot_plan", return_value={"id": "snap"})
    @patch("features.csr_plan_management.csr_plans_routes.audit_delete")
    @patch("features.csr_plan_management.csr_plans_routes._plan_is_editable", return_value=True)
    @patch("features.csr_plan_management.csr_plans_routes._user_can_access_site", return_value=True)
    def test_delete_plan_site_level1_success(self, _access, _editable, _audit, _snapshot):
        plan = SimpleNamespace(id="p-del-ok", site_id="s-1", year=2026, status="DRAFT")
        fake_plan_model = SimpleNamespace(query=MagicMock())
        fake_plan_model.query.get.return_value = plan
        fake_activity_model = object()

        with patch("features.csr_plan_management.csr_plans_routes.CsrPlan", fake_plan_model), patch(
            "models.CsrActivity", fake_activity_model
        ), patch.object(routes.db.session, "query") as mock_q, patch.object(routes.db.session, "delete"), patch.object(
            routes.db.session, "commit"
        ):
            mock_q.return_value.filter_by.return_value.delete.return_value = None
            with self._ctx("DELETE", "/api/csr-plans/p-del-ok", role="SITE_USER", user_id="site-l1"):
                response, status = routes.delete_plan.__wrapped__("p-del-ok")
        self.assertEqual(status, 200)
        self.assertIn("supprim", response.get_json()["message"].lower())


if __name__ == "__main__":
    unittest.main()

