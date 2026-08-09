#!/usr/bin/env python3
"""
Tests for dashboard.py — DashboardGenerator and data containers.

Tests cover:
- JSON loading and error handling
- Generation/Script data classes
- Each chart/section method (fitness, scripts, scenarios, strategy, timeline, complexity, LLM log)
- Empty/missing data handling
- HTML output structure
- CLI entry point
"""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from dashboard import DashboardGenerator, Generation, Script, main


# ─── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def sample_history():
    """A well-formed history dict for testing."""
    return {
        "fitness": [
            {"index": 0, "best": 0.5, "avg": 0.3, "worst": 0.1},
            {"index": 1, "best": 0.7, "avg": 0.5, "worst": 0.2},
            {"index": 2, "best": 0.9, "avg": 0.6, "worst": 0.3},
        ],
        "top_scripts": [
            {"name": "aggressive_bot", "dsl": "attack repeat", "score": 42.5},
            {"name": "cautious_bot", "dsl": "flee if enemy", "score": 38.0},
            {"name": "explorer", "dsl": "explore; grab", "score": 35.2},
        ],
        "scenario_survival": [
            {"difficulty": 0.1, "survival_rate": 0.9},
            {"difficulty": 0.5, "survival_rate": 0.5},
            {"difficulty": 0.9, "survival_rate": 0.1},
        ],
        "strategy_distribution": {
            "attack": 30,
            "flee": 20,
            "explore": 50,
        },
        "breakthroughs": [
            {"generation": 1, "description": "Discovered attacking"},
            {"generation": 3, "description": "First use of combos"},
        ],
        "complexity_trend": [
            {"generation": 0, "avg_complexity": 5.0},
            {"generation": 1, "avg_complexity": 8.5},
            {"generation": 2, "avg_complexity": 12.0},
        ],
        "llm_scenarios": [
            "A dark room with a single exit",
            "An arena with three enemies",
        ],
    }


@pytest.fixture
def history_file(sample_history, tmp_path):
    """Write sample history to a temp JSON file."""
    p = tmp_path / "history.json"
    p.write_text(json.dumps(sample_history))
    return str(p)


@pytest.fixture
def empty_history_file(tmp_path):
    """An empty history dict."""
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({}))
    return str(p)


@pytest.fixture
def generator(history_file):
    return DashboardGenerator(history_file)


@pytest.fixture
def empty_generator(empty_history_file):
    return DashboardGenerator(empty_history_file)


# ─── Data class tests ───────────────────────────────────────────

class TestGeneration:
    def test_construction(self):
        g = Generation(5, 0.9, 0.5, 0.1)
        assert g.index == 5
        assert g.best == 0.9
        assert g.avg == 0.5
        assert g.worst == 0.1

    def test_zero_values(self):
        g = Generation(0, 0.0, 0.0, 0.0)
        assert g.index == 0
        assert g.best == 0.0


class TestScript:
    def test_construction(self):
        s = Script("bot", "attack", 10.0)
        assert s.name == "bot"
        assert s.dsl == "attack"
        assert s.score == 10.0

    def test_empty_name(self):
        s = Script("", "", 0.0)
        assert s.name == ""


# ─── Loading tests ──────────────────────────────────────────────

class TestLoading:
    def test_loads_valid_file(self, history_file):
        gen = DashboardGenerator(history_file)
        assert "fitness" in gen.history
        assert len(gen.history["fitness"]) == 3

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            DashboardGenerator(str(tmp_path / "nonexistent.json"))

    def test_invalid_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json {{{")
        with pytest.raises(json.JSONDecodeError):
            DashboardGenerator(str(p))


# ─── Fitness chart tests ────────────────────────────────────────

class TestFitnessChart:
    def test_returns_html_with_chart(self, generator):
        html = generator._fitness_chart()
        assert "fitnessChart" in html
        assert "canvas" in html

    def test_includes_labels(self, generator):
        html = generator._fitness_chart()
        assert "0" in html
        assert "1" in html
        assert "2" in html

    def test_includes_data_values(self, generator):
        html = generator._fitness_chart()
        # Best values should appear
        assert "0.5" in html or "0.9" in html

    def test_empty_fitness_returns_placeholder(self, empty_generator):
        html = empty_generator._fitness_chart()
        assert "No fitness data" in html


# ─── Scripts table tests ────────────────────────────────────────

class TestScriptsTable:
    def test_returns_html_table(self, generator):
        html = generator._scripts_table()
        assert "<table" in html
        assert "</table>" in html

    def test_includes_script_names(self, generator):
        html = generator._scripts_table()
        assert "aggressive_bot" in html
        assert "cautious_bot" in html

    def test_includes_dsl(self, generator):
        html = generator._scripts_table()
        assert "attack repeat" in html

    def test_empty_scripts_returns_placeholder(self, empty_generator):
        html = empty_generator._scripts_table()
        assert "No script data" in html


# ─── Scenario analysis tests ────────────────────────────────────

class TestScenarioAnalysis:
    def test_returns_html_with_chart(self, generator):
        html = generator._scenario_analysis()
        assert "scenarioChart" in html
        assert "canvas" in html

    def test_empty_returns_placeholder(self, empty_generator):
        html = empty_generator._scenario_analysis()
        assert "No scenario" in html


# ─── Strategy distribution tests ────────────────────────────────

class TestStrategyDistribution:
    def test_returns_html_with_chart(self, generator):
        html = generator._strategy_distribution()
        assert "strategyChart" in html

    def test_includes_labels(self, generator):
        html = generator._strategy_distribution()
        assert "attack" in html
        assert "flee" in html
        assert "explore" in html

    def test_empty_returns_placeholder(self, empty_generator):
        html = empty_generator._strategy_distribution()
        assert "No strategy" in html


# ─── Evolution timeline tests ───────────────────────────────────

class TestEvolutionTimeline:
    def test_returns_html_list(self, generator):
        html = generator._evolution_timeline()
        assert "<ul" in html or "<li" in html

    def test_includes_descriptions(self, generator):
        html = generator._evolution_timeline()
        assert "Discovered attacking" in html
        assert "First use of combos" in html

    def test_empty_returns_placeholder(self, empty_generator):
        html = empty_generator._evolution_timeline()
        assert "No breakthrough" in html


# ─── Complexity trend tests ─────────────────────────────────────

class TestComplexityTrend:
    def test_returns_html_with_chart(self, generator):
        html = generator._script_complexity_trend()
        assert "complexityChart" in html

    def test_empty_returns_placeholder(self, empty_generator):
        html = empty_generator._script_complexity_trend()
        assert "No complexity" in html


# ─── LLM scenario log tests ─────────────────────────────────────

class TestLLMScenarioLog:
    def test_returns_html_list(self, generator):
        html = generator._llm_scenario_log()
        assert "<li>" in html

    def test_includes_scenario_text(self, generator):
        html = generator._llm_scenario_log()
        assert "dark room" in html
        assert "three enemies" in html

    def test_empty_returns_placeholder(self, empty_generator):
        html = empty_generator._llm_scenario_log()
        assert "No LLM scenario" in html


# ─── Full page assembly tests ───────────────────────────────────

class TestBuildPage:
    def test_returns_full_html_document(self, generator):
        html = generator._build_page()
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

    def test_includes_chart_js_cdn(self, generator):
        html = generator._build_page()
        assert "chart.js" in html.lower()

    def test_includes_css(self, generator):
        html = generator._build_page()
        assert "<style>" in html
        assert "font-family" in html

    def test_includes_title(self, generator):
        html = generator._build_page()
        assert "MUD Arena" in html

    def test_empty_page_still_valid_html(self, empty_generator):
        html = empty_generator._build_page()
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html


# ─── Generate (file output) tests ───────────────────────────────

class TestGenerate:
    def test_writes_file(self, generator, tmp_path):
        out = str(tmp_path / "output.html")
        generator.generate(out)
        assert os.path.exists(out)

    def test_written_file_is_valid_html(self, generator, tmp_path):
        out = str(tmp_path / "output.html")
        generator.generate(out)
        content = open(out).read()
        assert "<!DOCTYPE html>" in content
        assert "</html>" in content

    def test_default_output_path(self, generator, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        generator.generate()
        assert os.path.exists("dashboard.html")


# ─── CLI entry point tests ──────────────────────────────────────

class TestCLI:
    def test_main_generates_file(self, history_file, tmp_path):
        out = str(tmp_path / "cli_output.html")
        sys.argv = ["dashboard.py", history_file, "-o", out]
        main()
        assert os.path.exists(out)

    def test_main_default_output(self, history_file, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sys.argv = ["dashboard.py", history_file]
        main()
        assert os.path.exists("dashboard.html")


# ─── Edge cases ─────────────────────────────────────────────────

class TestEdgeCases:
    def test_partial_data(self, tmp_path):
        """History with only some keys present."""
        p = tmp_path / "partial.json"
        p.write_text(json.dumps({"fitness": [{"index": 0, "best": 1.0, "avg": 0.5, "worst": 0.0}]}))
        gen = DashboardGenerator(str(p))
        html = gen._build_page()
        assert "<!DOCTYPE html>" in html
        # Only fitness should render; others should show placeholders
        assert "No script data" in html

    def test_more_than_10_scripts(self, tmp_path):
        """Top scripts should be limited to 10."""
        scripts = [{"name": f"bot_{i}", "dsl": "noop", "score": float(100 - i)} for i in range(15)]
        p = tmp_path / "many_scripts.json"
        p.write_text(json.dumps({"top_scripts": scripts}))
        gen = DashboardGenerator(str(p))
        html = gen._scripts_table()
        # Count rows — should be at most 10
        assert html.count("<tr><td>") <= 10
        assert "bot_0" in html
        assert "bot_14" not in html

    def test_missing_keys_treated_as_empty(self, tmp_path):
        """Completely empty dict should not crash."""
        p = tmp_path / "empty.json"
        p.write_text("{}")
        gen = DashboardGenerator(str(p))
        # All sections should return placeholders
        assert "No fitness" in gen._fitness_chart()
        assert "No script" in gen._scripts_table()
        assert "No scenario" in gen._scenario_analysis()
        assert "No strategy" in gen._strategy_distribution()
        assert "No breakthrough" in gen._evolution_timeline()
        assert "No complexity" in gen._script_complexity_trend()
        assert "No LLM" in gen._llm_scenario_log()
