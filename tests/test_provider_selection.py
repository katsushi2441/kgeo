"""無料枠はローカルGemma、課金された実行だけDeepSeekを使うことのテスト。

無料枠でDeepSeekを呼ぶとAPI原価がそのまま赤字になり、自社GPUを持っている
利点も消える。逆に課金された実行までGemmaにすると、待ち時間と品質で
有料の体験にならない。この境目を固定する。
"""

from __future__ import annotations

import pytest

from app import config, monitor_service


@pytest.fixture(autouse=True)
def admin_users(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_USERS", ("xb_bittensor",))


class TestProviderForRun:
    def test_free_run_uses_local_gemma(self):
        """無料枠の実行は自社GPU。API原価をかけない。"""
        assert monitor_service.provider_for("general_user", paid=False) == "ollama"

    def test_paid_run_uses_deepseek(self):
        """課金された実行はホスト型。待ち時間と品質を優先する。"""
        assert monitor_service.provider_for("general_user", paid=True) == "deepseek"

    def test_admin_always_uses_local_gemma(self):
        """管理者は内部利用。課金の有無にかかわらずGemma。"""
        assert monitor_service.provider_for("xb_bittensor", paid=True) == "ollama"
        assert monitor_service.provider_for("xb_bittensor", paid=False) == "ollama"

    def test_owner_is_normalized(self):
        """@付き・大文字でも管理者判定が効く。"""
        assert monitor_service.provider_for("@XB_Bittensor", paid=True) == "ollama"

    def test_default_is_paid_side(self):
        """引数を省いた呼び出しが無料扱いに倒れると、原価が漏れる。"""
        assert monitor_service.provider_for("general_user") == "deepseek"


class TestConfiguredFollowsProvider:
    def test_free_run_checks_rqdb4ai(self, monkeypatch):
        """無料枠はrqdb4ai(ローカルOllama)の設定を見る。"""
        monkeypatch.setattr(monitor_service.rqdb4ai_client, "configured", lambda: True)
        monkeypatch.setattr(config, "DEEPSEEK_BASE_URL", "")
        monkeypatch.setattr(config, "DEEPSEEK_MODEL", "")
        assert monitor_service.configured("general_user", paid=False) is True

    def test_paid_run_checks_deepseek(self, monkeypatch):
        """課金実行はDeepSeekの設定を見る。rqdb4aiが落ちていても判定は独立。"""
        monkeypatch.setattr(monitor_service.rqdb4ai_client, "configured", lambda: False)
        monkeypatch.setattr(config, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        monkeypatch.setattr(config, "DEEPSEEK_MODEL", "deepseek-v4-flash")
        monkeypatch.setattr(monitor_service, "deepseek_api_key", lambda: "key")
        assert monitor_service.configured("general_user", paid=True) is True

    def test_paid_run_without_deepseek_key_is_not_configured(self, monkeypatch):
        monkeypatch.setattr(config, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        monkeypatch.setattr(config, "DEEPSEEK_MODEL", "deepseek-v4-flash")
        monkeypatch.setattr(monitor_service, "deepseek_api_key", lambda: "")
        assert monitor_service.configured("general_user", paid=True) is False


class TestFreeQuotaBoundary:
    """usage_status が「次の1回が無料か」を正しく出すこと。"""

    @pytest.fixture()
    def main(self, monkeypatch):
        from app import db, main as main_module

        monkeypatch.setattr(config, "FREE_MONITOR_RUNS_PER_MONTH", 5)
        monkeypatch.setattr(db, "get_plan", lambda owner: "free")
        return main_module, db

    def test_within_quota_is_free(self, main, monkeypatch):
        main_module, db = main
        monkeypatch.setattr(db, "monthly_usage", lambda o, k, m: 4 if k == "monitor" else 0)
        assert main_module.within_free_quota("general_user", "monitor") is True

    def test_at_quota_is_paid(self, main, monkeypatch):
        """5回無料なら5回目を使い切った時点で次は課金＝DeepSeek。"""
        main_module, db = main
        monkeypatch.setattr(db, "monthly_usage", lambda o, k, m: 5 if k == "monitor" else 0)
        assert main_module.within_free_quota("general_user", "monitor") is False

    def test_admin_is_always_free(self, main, monkeypatch):
        main_module, db = main
        monkeypatch.setattr(db, "monthly_usage", lambda o, k, m: 999)
        assert main_module.within_free_quota("xb_bittensor", "monitor") is True


class TestAdminImpersonation:
    """管理者だけが他ユーザーのデータを代理操作できること。

    利用者が詰まったときに運営が手当てするための機能。誤って一般ユーザーに
    使えてしまうと、他人のデータを触れることになる。
    """

    @pytest.fixture()
    def app_client(self, tmp_path, monkeypatch):
        from tests.test_api import configure_test  # 既存の初期化を再利用
        from fastapi.testclient import TestClient
        from app import config as cfg, main as main_module

        configure_test(tmp_path, monkeypatch)
        monkeypatch.setattr(cfg, "INTERNAL_TOKEN", "tok")
        monkeypatch.setattr(cfg, "ADMIN_USERS", {"xb_bittensor"})
        # with を使わないと lifespan が走らず init_db されない
        with TestClient(main_module.app) as client:
            yield client

    def _headers(self, user, act_as=None):
        h = {"X-KGeo-Token": "tok", "X-KGeo-User": user}
        if act_as:
            h["X-KGeo-Act-As"] = act_as
        return h

    def test_admin_can_act_as_another_user(self, app_client):
        res = app_client.get("/api/sites", headers=self._headers("xb_bittensor", "alice"))
        assert res.status_code == 200

    def test_general_user_cannot_impersonate(self, app_client):
        """黙って自分のデータを返すと、代理できたと誤解したまま作業が進む。"""
        res = app_client.get("/api/sites", headers=self._headers("bob", "alice"))
        assert res.status_code == 403

    def test_acting_as_self_is_allowed(self, app_client):
        res = app_client.get("/api/sites", headers=self._headers("bob", "bob"))
        assert res.status_code == 200

    def test_invalid_act_as_is_rejected(self, app_client):
        res = app_client.get("/api/sites", headers=self._headers("xb_bittensor", "x" * 201))
        assert res.status_code == 400

    def test_admin_users_endpoint_requires_admin(self, app_client):
        assert app_client.get("/api/admin/users", headers=self._headers("bob")).status_code == 403
        assert app_client.get("/api/admin/users", headers=self._headers("xb_bittensor")).status_code == 200
