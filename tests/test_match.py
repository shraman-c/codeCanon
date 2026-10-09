from __future__ import annotations

import pytest

from drift.match import (
    match_claims,
    apply_image_discount,
    _normalize_route,
    _is_similar_prefix,
    _has_prefix_mismatch,
    _get_env_prefix,
)
from drift.models import Claim, Fact, Finding


def _claim(kind: str, text: str, source: str = "text", **kw) -> Claim:
    return Claim(
        kind=kind,
        text=text,
        doc_file="README.md",
        line=1,
        context="test context",
        source=source,
        **kw,
    )


def _fact(kind: str, name: str, detail: str = "") -> Fact:
    return Fact(kind=kind, name=name, detail=detail, file="package.json", line=1)


class TestRouteNormalization:
    def test_normalize_basic(self):
        assert _normalize_route("/api/users") == "/api/users"

    def test_normalize_trailing_slash(self):
        assert _normalize_route("/api/users/") == "/api/users"

    def test_normalize_next_param(self):
        assert _normalize_route("/api/[id]") == "/api/:param"

    def test_normalize_express_param(self):
        assert _normalize_route("/api/:id") == "/api/:param"

    def test_normalize_brace_param(self):
        assert _normalize_route("/api/{id}") == "/api/:param"

    def test_case_insensitive(self):
        assert _normalize_route("/API/USERS") == "/api/users"


class TestSimilarPrefix:
    def test_same_prefix_v2(self):
        assert _is_similar_prefix("/api/users", "/api/v2/users") is True

    def test_same_prefix_v3(self):
        assert _is_similar_prefix("/api/v1/users", "/api/v2/users") is True

    def test_different_prefix(self):
        assert _is_similar_prefix("/api/users", "/admin/users") is False

    def test_exact_match_false(self):
        assert _is_similar_prefix("/api/users", "/api/users") is False

    def test_too_short(self):
        assert _is_similar_prefix("/api", "/api/v2/users") is False


class TestEnvPrefix:
    def test_next_public(self):
        assert _get_env_prefix("NEXT_PUBLIC_API_URL") == "NEXT_PUBLIC_"

    def test_vite(self):
        assert _get_env_prefix("VITE_API_URL") == "VITE_"

    def test_react_app(self):
        assert _get_env_prefix("REACT_APP_KEY") == "REACT_APP_"

    def test_no_prefix(self):
        assert _get_env_prefix("DATABASE_URL") == ""

    def test_prefix_mismatch(self):
        assert _has_prefix_mismatch("NEXT_PUBLIC_API_URL", "VITE_API_URL") is True

    def test_no_mismatch_same(self):
        assert _has_prefix_mismatch("NEXT_PUBLIC_API_URL", "NEXT_PUBLIC_SITE_URL") is False

    def test_no_mismatch_one_empty(self):
        assert _has_prefix_mismatch("DATABASE_URL", "NEXT_PUBLIC_API_URL") is False


class TestNpmScriptMatching:
    def test_exact_match(self):
        claim = _claim("npm_script", "npm run dev")
        fact = _fact("npm_script", "dev", "next dev")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "OK"
        assert "exists in package.json" in findings[0].reason

    def test_builtin_script(self):
        claim = _claim("npm_script", "npm run start")
        findings = match_claims([claim], [])
        assert findings[0].status == "OK"
        assert "built-in" in findings[0].reason

    def test_fuzzy_suspect(self):
        claim = _claim("npm_script", "npm run dev:local")
        fact = _fact("npm_script", "dev", "next dev")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "SUSPECT"
        assert "similar" in findings[0].reason

    def test_fuzzy_below_threshold_stale(self):
        claim = _claim("npm_script", "npm run completelydifferent")
        fact = _fact("npm_script", "dev", "next dev")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "STALE"

    def test_no_facts_stale(self):
        claim = _claim("npm_script", "npm run missing")
        findings = match_claims([claim], [])
        assert findings[0].status == "STALE"


class TestEnvVarMatching:
    def test_exact_match(self):
        claim = _claim("env_var", "DATABASE_URL=postgres://...")
        fact = _fact("env_var", "DATABASE_URL", "server-side")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "OK"

    def test_allowlisted(self):
        claim = _claim("env_var", "NODE_ENV=production")
        findings = match_claims([claim], [])
        assert findings[0].status == "OK"
        assert "allowlisted" in findings[0].reason

    def test_fuzzy_suspect(self):
        claim = _claim("env_var", "DATABASE_URL=postgres://...")
        fact = _fact("env_var", "DATABASE_URI", "server-side")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "SUSPECT"

    def test_prefix_mismatch_suspect(self):
        claim = _claim("env_var", "NEXT_PUBLIC_API_URL=...")
        fact = _fact("env_var", "VITE_API_URL", "client-exposed (Vite)")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "SUSPECT"
        assert "different prefix" in findings[0].reason

    def test_not_found_stale(self):
        claim = _claim("env_var", "MISSING_VAR=...")
        findings = match_claims([claim], [])
        assert findings[0].status == "STALE"


class TestPortMatching:
    def test_exact_match(self):
        claim = _claim("port", "localhost:3000")
        fact = _fact("port", "3000", "listen(3000)")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "OK"

    def test_port_in_detail(self):
        claim = _claim("port", "PORT=8080")
        fact = _fact("port", "8080", "PORT || 8080")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "OK"

    def test_ambiguous_multiple(self):
        claim = _claim("port", "localhost:3000")
        facts = [_fact("port", "3000", "listen(3000)"), _fact("port", "3000", "vite port 3000")]
        findings = match_claims([claim], facts)
        assert findings[0].status == "SUSPECT"
        assert "multiple" in findings[0].reason

    def test_not_found_stale(self):
        claim = _claim("port", "localhost:9999")
        fact = _fact("port", "3000", "listen(3000)")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "STALE"


class TestEngineMatching:
    def test_satisfies_engine(self):
        claim = _claim("engine", "node 20.10.0")
        fact = _fact("engine", "node", ">=20")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "OK"

    def test_below_minimum_stale(self):
        claim = _claim("engine", "node 16.14.0")
        fact = _fact("engine", "node", ">=20")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "STALE"

    def test_no_engine_facts_ok(self):
        claim = _claim("engine", "node 16.14.0")
        findings = match_claims([claim], [])
        assert findings[0].status == "OK"
        assert "skipping" in findings[0].reason


class TestRouteMatching:
    def test_exact_match(self):
        claim = _claim("route", "GET /api/users")
        fact = _fact("route", "/api/users", "GET,POST")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "OK"

    def test_param_normalization(self):
        claim = _claim("route", "GET /api/users/123")
        fact = _fact("route", "/api/users/:id", "GET")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "OK"

    def test_next_param_style(self):
        claim = _claim("route", "GET /api/users/[id]")
        fact = _fact("route", "/api/users/:id", "GET")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "OK"

    def test_method_mismatch_suspect(self):
        claim = _claim("route", "POST /api/users")
        fact = _fact("route", "/api/users", "GET")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "SUSPECT"
        assert "method differs" in findings[0].reason

    def test_similar_prefix_suspect(self):
        claim = _claim("route", "GET /api/users")
        fact = _fact("route", "/api/v2/users", "GET")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "SUSPECT"
        assert "similar" in findings[0].reason

    def test_not_found_stale(self):
        claim = _claim("route", "GET /api/missing")
        fact = _fact("route", "/api/users", "GET")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "STALE"


class TestDependencyMatching:
    def test_exact_match(self):
        claim = _claim("dependency", "react")
        fact = _fact("dependency", "react", "^18")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "OK"

    def test_fuzzy_suspect(self):
        claim = _claim("dependency", "reactt")
        fact = _fact("dependency", "react", "^18")
        findings = match_claims([claim], [fact])
        assert findings[0].status == "SUSPECT"

    def test_not_found_stale(self):
        claim = _claim("dependency", "missing-pkg")
        findings = match_claims([claim], [])
        assert findings[0].status == "STALE"


class TestAllowlist:
    def test_generic_allowlist(self):
        claim = _claim("npm_script", "--help")
        findings = match_claims([claim], [])
        assert findings[0].status == "OK"

    def test_localhost_allowlist(self):
        claim = _claim("port", "localhost")
        findings = match_claims([claim], [])
        assert findings[0].status == "OK"

    def test_placeholder_allowlist(self):
        claim = _claim("env_var", "YOUR_API_KEY=xxx")
        findings = match_claims([claim], [])
        assert findings[0].status == "OK"

    def test_angle_bracket_placeholder(self):
        claim = _claim("env_var", "<your-token>=abc")
        findings = match_claims([claim], [])
        assert findings[0].status == "OK"

    def test_xxx_placeholder(self):
        claim = _claim("env_var", "xxx")
        findings = match_claims([claim], [])
        assert findings[0].status == "OK"


class TestImageDiscount:
    def test_stale_downgraded_short_quote(self):
        claim = _claim("npm_script", "npm run old", source="image", extracted_text="$ npm run old")
        fact = _fact("npm_script", "dev", "next dev")
        findings = match_claims([claim], [fact])
        findings = apply_image_discount(findings)
        assert findings[0].status == "SUSPECT"
        assert "downgraded" in findings[0].reason

    def test_stale_not_downgraded_long_quote(self):
        claim = _claim(
            "npm_script",
            "npm run old",
            source="image",
            extracted_text="$ npm run old\nready on http://localhost:3000\nserver started",
        )
        fact = _fact("npm_script", "dev", "next dev")
        findings = match_claims([claim], [fact])
        findings = apply_image_discount(findings)
        assert findings[0].status == "STALE"

    def test_ok_not_downgraded(self):
        claim = _claim("npm_script", "npm run dev", source="image", extracted_text="$ npm run dev")
        fact = _fact("npm_script", "dev", "next dev")
        findings = match_claims([claim], [fact])
        findings = apply_image_discount(findings)
        assert findings[0].status == "OK"

    def test_suspect_not_downgraded(self):
        claim = _claim("npm_script", "npm run dev:local", source="image", extracted_text="$ npm run dev:local")
        fact = _fact("npm_script", "dev", "next dev")
        findings = match_claims([claim], [fact])
        findings = apply_image_discount(findings)
        assert findings[0].status == "SUSPECT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])