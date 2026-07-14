"""Tests pour la consolidation de l'observation masking.

Valide:
- La nouvelle heuristique _looks_like_error_tool_content (faux positifs éliminés)
- Le helper build_mask_policy_from_config
"""
from __future__ import annotations


from kimi_proxy.features.observation_masking.schema1 import _looks_like_error_tool_content
from kimi_proxy.features.observation_masking import build_mask_policy_from_config, MaskPolicy


# ── Tests _looks_like_error_tool_content ─────────────────────────────────────

class TestLooksLikeErrorToolContent:
    """Vérifie les heuristiques consolidées de détection d'erreur."""

    # --- Vrais positifs (doivent retourner True) ---

    def test_python_traceback(self):
        content = "Traceback (most recent call last):\n  File \"main.py\", line 1\nValueError: bad"
        assert _looks_like_error_tool_content(content) is True

    def test_raise_statement(self):
        content = "  raise ValueError('invalid input')"
        assert _looks_like_error_tool_content(content) is True

    def test_error_colon_prefix(self):
        content = "Error: fichier non trouvé"
        assert _looks_like_error_tool_content(content) is True

    def test_fatal_error(self):
        content = "Fatal Error during compilation"
        assert _looks_like_error_tool_content(content) is True

    def test_json_error_key(self):
        content = '{"error": "something went wrong"}'
        assert _looks_like_error_tool_content(content) is True

    def test_json_status_error(self):
        content = '{"status": "error", "message": "oops"}'
        assert _looks_like_error_tool_content(content) is True

    # --- Faux positifs éliminés (doivent retourner False) ---

    def test_timeout_in_normal_content_no_false_positive(self):
        """Le mot 'timeout' dans du contenu légitime ne déclenche plus l'heuristique."""
        content = "The default timeout for HTTP requests is 30 seconds. Configure it in settings."
        assert _looks_like_error_tool_content(content) is False

    def test_exception_in_docs_no_false_positive(self):
        """Le mot 'exception' dans de la documentation ne déclenche plus."""
        content = "This function raises an exception if the input is invalid. See docs for details."
        assert _looks_like_error_tool_content(content) is False

    def test_connection_refused_in_docs_no_false_positive(self):
        """'connection refused' dans un texte explicatif ne déclenche plus."""
        content = "If you see 'connection refused', check that the server is running."
        assert _looks_like_error_tool_content(content) is False

    def test_connect_error_in_normal_text_no_false_positive(self):
        """'connect_error' dans du code source normal ne déclenche plus."""
        content = "status_codes = ['connect_error', 'success', 'pending']"
        assert _looks_like_error_tool_content(content) is False

    # --- Cas limites ---

    def test_empty_string(self):
        assert _looks_like_error_tool_content("") is False

    def test_none(self):
        assert _looks_like_error_tool_content(None) is False

    def test_non_string(self):
        assert _looks_like_error_tool_content(42) is False

    def test_short_normal_content(self):
        assert _looks_like_error_tool_content("OK") is False

    def test_json_without_error_key(self):
        content = '{"result": "success", "data": [1, 2, 3]}'
        assert _looks_like_error_tool_content(content) is False

    def test_json_status_success_not_error(self):
        content = '{"status": "success"}'
        assert _looks_like_error_tool_content(content) is False

    def test_invalid_json_starting_with_brace(self):
        content = '{not valid json at all'
        assert _looks_like_error_tool_content(content) is False


# ── Tests build_mask_policy_from_config ──────────────────────────────────────

class TestBuildMaskPolicyFromConfig:
    """Vérifie la construction centralisée de MaskPolicy depuis la config."""

    def test_from_dataclass_config(self):
        """Construit un MaskPolicy depuis une dataclass config standard."""
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class FakeConfig:
            enabled: bool = True
            window_turns: int = 4
            keep_errors: bool = False
            keep_last_k_per_tool: int = 2
            placeholder_template: str = "masked"

        cfg = FakeConfig()
        policy = build_mask_policy_from_config(cfg)
        assert isinstance(policy, MaskPolicy)
        assert policy.enabled is True
        assert policy.window_turns == 4
        assert policy.keep_errors is False
        assert policy.keep_last_k_per_tool == 2
        assert policy.placeholder_template == "masked"

    def test_defaults_on_missing_attrs(self):
        """Retombe sur les defaults si les attributs manquent."""
        policy = build_mask_policy_from_config(object())
        assert isinstance(policy, MaskPolicy)
        assert policy.enabled is False
        assert policy.window_turns == 8
        assert policy.keep_errors is True

    def test_from_real_loader_config(self):
        """Fonctionne avec la vraie ObservationMaskingSchema1Config."""
        from kimi_proxy.config.loader import ObservationMaskingSchema1Config
        cfg = ObservationMaskingSchema1Config(enabled=True, window_turns=5)
        policy = build_mask_policy_from_config(cfg)
        assert policy.enabled is True
        assert policy.window_turns == 5
