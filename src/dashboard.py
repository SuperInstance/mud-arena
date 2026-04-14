Below is a **stand‑alone Python module** that reads a JSON file containing the whole evolution history of a MUD‑Arena back‑test and writes a single, self‑contained HTML file.  
The HTML page uses only **pure HTML + CSS + JavaScript** (Chart.js is loaded from a CDN) – no web‑server or extra Python packages are required.

---

## 1.  Expected JSON structure  

The script does not enforce a rigid schema, but it expects the following top‑level keys (all of them are optional – missing data will simply be omitted from the dashboard).

| Key | Meaning | Example fragment |
|-----|---------|------------------|
| `fitness` | List of generations, each with `index`, `best`, `avg`, `worst` | `[{ "index":0, "best":95, "avg":45, "worst":5 }, …]` |
| `top_scripts` | List of scripts sorted by score (best first). Each entry has `name`, `dsl`, `score` | `[{ "name":"S1", "dsl":"attack;move north", "score":92.3 }, …]` |
| `scenario_survival` | List of objects `{ "difficulty": <float>, "survival_rate": <float> }` | `[{ "difficulty":0.2, "survival_rate":0.85 }, …]` |
| `strategy_distribution` | Mapping `strategy → count` (e.g. `"attack": 120`) | `{ "attack":120, "flee":45, "explore":35 }` |
| `breakthroughs` | List of objects `{ "generation": <int>, "description": <str> }` | `[{ "generation":12, "description":"first script > 90 % win‑rate" }, …]` |
| `complexity_trend` | List of objects `{ "generation": <int>, "avg_complexity": <float> }` (complexity can be lines of DSL, AST nodes, …) | `[{ "generation":0, "avg_complexity":23.5 }, …]` |
| `llm_scenarios` | List of strings – the raw scenario prompts the LLM generated | `["You are in a dark cave …", "A dragon blocks the exit …"]` |

Feel free to add extra fields – the dashboard will simply ignore anything it does not recognise.

---

## 2.  The Python module  

```python
#!/usr/bin/env python3
"""
dashboard_generator.py

Generate a single‑file HTML dashboard for MUD‑Arena back‑testing results.
The dashboard visualises:

1. Generation fitness (best / avg / worst)
2. Top‑10 scripts (DSL + score)
3. Scenario difficulty vs script survival rate
4. Strategy distribution (attack / flee / explore)
5. Evolution timeline (breakthroughs)
6. Script‑complexity trend
7. LLM‑generated scenario log

All charts are rendered with Chart.js (loaded from a CDN). No server
or additional Python dependencies are required.
"""

import json
import pathlib
from typing import Any, Dict, List, Tuple


# ----------------------------------------------------------------------
# Helper data containers (purely for readability)
# ----------------------------------------------------------------------
class Generation:
    def __init__(self, index: int, best: float, avg: float, worst: float):
        self.index = index
        self.best = best
        self.avg = avg
        self.worst = worst


class Script:
    def __init__(self, name: str, dsl: str, score: float):
        self.name = name
        self.dsl = dsl
        self.score = score


# ----------------------------------------------------------------------
# Main class
# ----------------------------------------------------------------------
class DashboardGenerator:
    """
    Load a JSON file that contains the evolution history and produce a
    self‑contained HTML dashboard.
    """

    def __init__(self, history_path: str):
        """Read the JSON file into ``self.history``."""
        with open(history_path, "r", encoding="utf-8") as f:
            self.history: Dict[str, Any] = json.load(f)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self, output_path: str = "dashboard.html") -> None:
        """
        Build the full HTML page and write it to *output_path*.
        """
        html = self._build_page()
        pathlib.Path(output_path).write_text(html, encoding="utf-8")
        print(f"[+] Dashboard written to {output_path}")

    # ------------------------------------------------------------------
    # Private helpers – each returns a *string* that will be inserted into
    # the final HTML page.
    # ------------------------------------------------------------------
    def _fitness_chart(self) -> str:
        """Line chart: best / avg / worst fitness per generation."""
        gens_raw = self.history.get("fitness", [])
        generations = [
            Generation(
                int(g.get("index", 0)),
                float(g.get("best", 0)),
                float(g.get("avg", 0)),
                float(g.get("worst", 0)),
            )
            for g in gens_raw
        ]

        # If there is no data we simply return an empty placeholder.
        if not generations:
            return "<p>No fitness data available.</p>"

        labels = [str(g.index) for g in generations]
        best = [g.best for g in generations]
        avg = [g.avg for g in generations]
        worst = [g.worst for g in generations]

        # The JavaScript snippet that creates the chart.
        return f"""
        <canvas id="fitnessChart" height="200"></canvas>
        <script>
            const ctxFit = document.getElementById('fitnessChart').getContext('2d');
            new Chart(ctxFit, {{
                type: 'line',
                data: {{
                    labels: {json.dumps(labels)},
                    datasets: [
                        {{
                            label: 'Best',
                            data: {json.dumps(best)},
                            borderColor: 'rgb(255,99,132)',
                            backgroundColor: 'rgba(255,99,132,0.2)',
                            fill: false,
                            tension: 0.1
                        }},
                        {{
                            label: 'Average',
                            data: {json.dumps(avg)},
                            borderColor: 'rgb(54,162,235)',
                            backgroundColor: 'rgba(54,162,235,0.2)',
                            fill: false,
                            tension: 0.1
                        }},
                        {{
                            label: 'Worst',
                            data: {json.dumps(worst)},
                            borderColor: 'rgb(75,192,192)',
                            backgroundColor: 'rgba(75,192,192,0.2)',
                            fill: false,
                            tension: 0.1
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'Generation Fitness'
                        }},
                        legend: {{ position: 'top' }}
                    }},
                    scales: {{
                        x: {{ title: {{ display: true, text: 'Generation' }} }},
                        y: {{ title: {{ display: true, text: 'Fitness' }} }}
                    }}
                }}
            }});
        </script>
        """

    def _scripts_table(self) -> str:
        """HTML table with the top‑10 scripts (name, DSL, score)."""
        raw = self.history.get("top_scripts", [])
        scripts = [
            Script(
                str(s.get("name", "")),
                str(s.get("dsl", "")),
                float(s.get("score", 0)),
            )
            for s in raw
        ]

        if not scripts:
            return "<p>No script data available.</p>"

        rows = "\n".join(
            f"<tr><td>{s.name}</td><td><code>{s.dsl}</code></td><td>{s.score:.2f}</td></tr>"
            for s in scripts[:10]
        )
        return f"""
        <h2>Top‑10 Scripts</h2>
        <table class="striped">
            <thead><tr><th>Name</th><th>DSL</th><th>Score</th></tr></thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        """

    def _scenario_analysis(self) -> str:
        """Scatter / line chart: difficulty vs survival rate."""
        data = self.history.get("scenario_survival", [])
        if not data:
            return "<p>No scenario‑survival data available.</p>"

        # Sort by difficulty for a nicer line chart
        data = sorted(data, key=lambda x: float(x.get("difficulty", 0)))
        difficulties = [float(d.get("difficulty", 0)) for d in data]
        survivals = [float(d.get("survival_rate", 0)) for d in data]

        return f"""
        <h2>Scenario Difficulty vs Survival Rate</h2>
        <canvas id="scenarioChart" height="200"></canvas>
        <script>
            const ctxSc = document.getElementById('scenarioChart').getContext('2d');
            new Chart(ctxSc, {{
                type: 'line',
                data: {{
                    labels: {json.dumps(difficulties)},
                    datasets: [{{
                        label: 'Survival Rate',
                        data: {json.dumps(survivals)},
                        borderColor: 'rgb(153,102,255)',
                        backgroundColor: 'rgba(153,102,255,0.2)',
                        fill: false,
                        tension: 0.2,
                        pointRadius: 4
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        title: {{ display: true, text: 'Difficulty → Survival' }},
                        tooltip: {{ callbacks: {{
                            label: ctx => `Survival: ${(ctx.parsed.y*100).toFixed(1)}%`
                        }}}}
                    }},
                    scales: {{
                        x: {{
                            title: {{ display: true, text: 'Scenario Difficulty (0‑1)' }},
                            type: 'linear'
                        }},
                        y: {{
                            title: {{ display: true, text: 'Survival Rate (0‑1)' }},
                            min: 0,
                            max: 1
                        }}
                    }}
                }}
            }});
        </script>
        """

    def _strategy_distribution(self) -> str:
        """Pie chart showing % of scripts that use each high‑level strategy."""
        raw = self.history.get("strategy_distribution", {})
        if not raw:
            return "<p>No strategy distribution data available.</p>"

        # Convert counts → percentages
        total = sum(int(v) for v in raw.values())
        labels = list(raw.keys())
        counts = [int(raw[l]) for l in labels]
        percentages = [round(c / total * 100, 1) for c in counts]

        return f"""
        <h2>Strategy Distribution</h2>
        <canvas id="strategyChart" height="200"></canvas>
        <script>
            const ctxStr = document.getElementById('strategyChart').getContext('2d');
            new Chart(ctxStr, {{
                type: 'pie',
                data: {{
                    labels: {json.dumps(labels)},
                    datasets: [{{
                        data: {json.dumps(percentages)},
                        backgroundColor: [
                            'rgb(255,99,132)',
                            'rgb(255,159,64)',
                            'rgb(255,205,86)',
                            'rgb(75,192,192)',
                            'rgb(54,162,235)',
                            'rgb(153,102,255)'
                        ]
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        title: {{ display: true, text: 'Strategy Usage (%)' }},
                        tooltip: {{
                            callbacks: {{
                                label: ctx => `${{ctx.label}}: ${{ctx.parsed}}%`
                            }}
                        }}
                    }}
                }}
            }});
        </script>
        """

    def _evolution_timeline(self) -> str:
        """Vertical timeline (simple list) of breakthrough generations."""
        events = self.history.get("breakthroughs", [])
        if not events:
            return "<p>No breakthrough data available.</p>"

        # Sort chronologically
        events = sorted(events, key=lambda e: int(e.get("generation", 0)))
        items = "\n".join(
            f"<li><strong>Gen {e.get('generation')}</strong>: {e.get('description','')}</li>"
            for e in events
        )
        return f"""
        <h2>Evolution Timeline</h2>
        <ul class="timeline">
            {items}
        </ul>
        """

    def _script_complexity_trend(self) -> str:
        """Line chart: average script complexity per generation."""
        raw = self.history.get("complexity_trend", [])
        if not raw:
            return "<p>No complexity‑trend data available.</p>"

        raw = sorted(raw, key=lambda x: int(x.get("generation", 0)))
        generations = [int(x.get("generation")) for x in raw]
        complexities = [float(x.get("avg_complexity")) for x in raw]

        return f"""
        <h2>Script Complexity Trend</h2>
        <canvas id="complexityChart" height="200"></canvas>
        <script>
            const ctxComp = document.getElementById('complexityChart').getContext('2d');
            new Chart(ctxComp, {{
                type: 'line',
                data: {{
                    labels: {json.dumps(generations)},
                    datasets: [{{
                        label: 'Avg. Complexity',
                        data: {json.dumps(complexities)},
                        borderColor: 'rgb(255,159,64)',
                        backgroundColor: 'rgba(255,159,64,0.2)',
                        fill: false,
                        tension: 0.2
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        title: {{ display: true, text: 'Complexity Over Generations' }}
                    }},
                    scales: {{
                        x: {{ title: {{ display: true, text: 'Generation' }} }},
                        y: {{ title: {{ display: true, text: 'Complexity (e.g. # DSL tokens)' }} }}
                    }}
                }}
            }});
        </script>
        """

    def _llm_scenario_log(self) -> str:
        """Simple pre‑formatted block that lists every LLM‑generated scenario."""
        logs = self.history.get("llm_scenarios", [])
        if not logs:
            return "<p>No LLM scenario log available.</p>"

        items = "\n".join(f"<li><code>{s}</code></li>" for s in logs)
        return f"""
        <h2>LLM‑Generated Scenario Log</h2>
        <ol class="scenario-log">
            {items}
        </ol>
        """

    # ------------------------------------------------------------------
    # Assemble the final HTML page
    # ------------------------------------------------------------------
    def _build_page(self) -> str:
        """Collect all fragments and wrap them in a full HTML document."""
        # Inline CSS – feel free to extend / replace with your own stylesheet
        css = """
        body {font-family: Arial, Helvetica, sans-serif; margin:0; padding:0 2rem; background:#fafafa;}
        h1, h2 {color:#333;}
        canvas {background:#fff; border:1px solid #ddd; margin-bottom:2rem;}
        table {border-collapse:collapse; width:100%; margin-bottom:2rem;}
        th, td {border:1px solid #ccc; padding:0.5rem; text-align:left;}
        th {background:#eee;}
        .striped tbody tr:nth-child(odd) {background:#f9f9f9;}
        .timeline {list-style:none; padding-left:0;}
        .timeline li {margin:0.5rem 0; padding-left:1rem; border-left:3px solid #6c5ce7;}
        .scenario-log {font-family:monospace; background:#fff; padding:1rem; border:1px solid #ddd;}
        """

        # Build each section – if a section returns an empty string we simply skip it.
        sections: List[Tuple[str, str]] = [
            ("Fitness Chart", self._fitness_chart()),
            ("Top Scripts", self._scripts_table()),
            ("Scenario Analysis", self._scenario_analysis()),
            ("Strategy Distribution", self._strategy_distribution()),
            ("Evolution Timeline", self._evolution_timeline()),
            ("Complexity Trend", self._script_complexity_trend()),
            ("LLM Scenario Log", self._llm_scenario_log()),
        ]

        body = "\n".join(
            f"<section>{content}</section>" for title, content in sections if content.strip()
        )

        # Final HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MUD Arena Back‑testing Dashboard</title>
    <style>{css}</style>
</head>
<body>
    <h1>MUD Arena Back‑testing Dashboard</h1>
    {body}
    <!-- Chart.js from CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</body>
</html>"""
        return html


# ----------------------------------------------------------------------
# Command‑line entry point
# ----------------------------------------------------------------------
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate a static HTML dashboard from a MUD‑Arena evolution JSON file."
    )
    parser.add_argument(
        "history",
        help="Path to the JSON file that contains the evolution history.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="dashboard.html",
        help="File name for the generated HTML (default: dashboard.html).",
    )
    args = parser.parse_args()

    generator = DashboardGenerator(args.history)
    generator.generate(args.output)


if __name__ == "__main__":
    main()
```

---

### How to use it

1. **Save the script** (e.g. `dashboard_generator.py`).  
2. **Prepare the JSON** file (`history.json`) following the structure described in section 1.  
3. Run the generator from the command line:

```bash
python dashboard_generator.py history.json -o my_dashboard.html
```

4. Open `my_dashboard.html` in any modern browser – all charts are rendered client‑side, no web server is required.

Feel free to adapt the CSS, add more sections, or change the chart types – the module is deliberately kept simple and extensible. Enjoy visualising your MUD‑Arena evolution!