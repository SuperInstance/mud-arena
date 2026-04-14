Below is a **self‑contained Python module** that implements the “set‑it‑and‑watch‑the‑game‑go” evolution engine for the MUD Arena.  
It follows every step you listed, supports optional GPU acceleration (via PyTorch), uses tournament selection, performs crossover‑/mutation‑based breeding, replaces the worst performers, and contains hooks for LLM‑based review and adaptive scenario generation.

Save the file as **`evolve.py`** and run it from the command line, e.g.:

```bash
python evolve.py --generations 100 --population 200 --scenarios 20
```

```python
#!/usr/bin/env python3
"""
evolve.py – Evolution Engine for the MUD Arena

Features
--------
* Random initial population of “scripts” (represented as rule lists)
* Evaluation of every script on a batch of scenarios (GPU‑accelerated when possible)
* Tournament selection of elite scripts
* Crossover‑based breeding + per‑gene mutation
* Replacement of the worst performers with newly‑born children
* Adaptive scenario generation (harder scenarios as fitness improves)
* Optional LLM‑review hooks (place‑holders for your own LLM integration)
* CLI interface for quick experiments
* Export / import of the whole population (pickle)

The engine is deliberately generic – you only have to plug in the
real MUD‑Arena specific logic for:

* ``Script.evaluate(scenario)`` – returns a numeric score / survival time
* ``generate_random_rules()`` – creates a random rule set
* ``generate_scenarios(n)`` – creates a list of scenario objects
* ``llm_review(best_scripts)`` – let an LLM suggest rule improvements
* ``llm_generate_harder_scenarios(best_scripts, n)`` – let an LLM craft
  tougher challenges

All other machinery (selection, breeding, mutation, statistics, CLI)
is ready to use.
"""

import argparse
import copy
import os
import pickle
import random
import sys
from collections import Counter
from typing import List, Tuple, Any, Dict

import numpy as np

# ----------------------------------------------------------------------
# Optional GPU support -------------------------------------------------
# ----------------------------------------------------------------------
try:
    import torch
    _GPU_AVAILABLE = torch.cuda.is_available()
except Exception:          # pragma: no cover
    _GPU_AVAILABLE = False

# ----------------------------------------------------------------------
# Helper – a very simple representation of a “script”
# ----------------------------------------------------------------------
class Script:
    """
    A script is a list of integer “rules”.  In a real MUD‑Arena
    implementation each rule would be a more complex object (e.g.
    a small program, a decision tree, etc.).  For the purpose of this
    generic engine we keep it simple – the engine only needs to be able
    to copy, crossover and mutate the rule list.
    """

    def __init__(self, rules: List[int]):
        self.rules = rules                     # list[int]

    # ------------------------------------------------------------------
    # USER‑DEFINED: replace with real evaluation logic
    # ------------------------------------------------------------------
    def evaluate(self, scenario: Any) -> float:
        """
        Evaluate this script on a single scenario.
        Must return a numeric fitness (higher = better).

        The stub below simply scores the script by counting how many
        rules match the scenario’s “target” value.  Replace with your
        actual MUD‑Arena simulation.
        """
        # Example placeholder: scenario is an int, rule matches if equal
        return sum(1 for r in self.rules if r == scenario)

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def copy(self) -> "Script":
        """Deep copy of the script."""
        return Script(self.rules.copy())

    def __len__(self) -> int:
        return len(self.rules)

    def __repr__(self) -> str:
        return f"Script(rules={self.rules})"


# ----------------------------------------------------------------------
# Evolution Engine -----------------------------------------------------
# ----------------------------------------------------------------------
class EvolutionEngine:
    """
    Core evolution engine.  All public methods match the signatures you
    asked for.
    """

    # ------------------------------------------------------------------
    def __init__(
        self,
        population_size: int = 100,
        elite_size: int = 10,
        mutation_rate: float = 0.1,
        tournament_size: int = 5,
        rule_length: int = 20,
        rule_range: Tuple[int, int] = (0, 100),
    ):
        self.population_size = population_size
        self.elite_size = elite_size                # K in your description
        self.mutation_rate = mutation_rate
        self.tournament_size = tournament_size
        self.rule_length = rule_length
        self.rule_range = rule_range                # inclusive bounds for random rules

        self.population: List[Script] = []
        self.generation: int = 0
        self.history: List[Dict[str, float]] = []   # fitness stats per generation

    # ------------------------------------------------------------------
    # 1️⃣  Initialise population ------------------------------------------------
    def initialize(self, seed_scripts: List[Script] = None) -> None:
        """Create the initial population.  If ``seed_scripts`` is supplied it
        is used (truncated / padded to ``population_size``).  Otherwise a
        random population is generated."""
        if seed_scripts:
            # Use provided scripts, fill up with random ones if needed
            self.population = [s.copy() for s in seed_scripts[: self.population_size]]
            while len(self.population) < self.population_size:
                self.population.append(Script(self._random_rules()))
        else:
            self.population = [Script(self._random_rules()) for _ in range(self.population_size)]

    # ------------------------------------------------------------------
    # Helper – generate a random rule list ------------------------------------
    def _random_rules(self) -> List[int]:
        low, high = self.rule_range
        return [random.randint(low, high) for _ in range(self.rule_length)]

    # ------------------------------------------------------------------
    # 2️⃣  Evaluate all scripts on a batch of scenarios ------------------------
    def evaluate(self, scenarios: List[Any], gpu: bool = True) -> List[float]:
        """
        Run every script against every scenario and return a list of
        average fitness scores (one per script).

        If ``gpu`` is True and a CUDA device is available, the evaluation
        is performed with PyTorch tensors for speed.  The stub implementation
        does not need GPU, but the structure is ready for you to replace
        ``Script.evaluate`` with a torch‑based simulation.
        """
        use_gpu = gpu and _GPU_AVAILABLE
        fitness = []

        if use_gpu:
            # ------------------------------------------------------------------
            # Example GPU‑accelerated evaluation (replace with real logic)
            # ------------------------------------------------------------------
            # Convert scenarios to a tensor
            scenario_tensor = torch.tensor(scenarios, device="cuda")
            for script in self.population:
                # Convert script rules to tensor
                rule_tensor = torch.tensor(script.rules, device="cuda")
                # Dummy scoring: count matches (broadcast)
                matches = (rule_tensor.unsqueeze(1) == scenario_tensor).float()
                score = matches.sum(dim=0).mean().item()
                fitness.append(score)
        else:
            # CPU path – simple Python loops
            for script in self.population:
                total = 0.0
                for sc in scenarios:
                    total += script.evaluate(sc)
                fitness.append(total / len(scenarios))

        return fitness

    # ------------------------------------------------------------------
    # 3️⃣  Tournament selection (returns list of elite scripts) ----------------
    def select(self, fitness: List[float]) -> List[Script]:
        """
        Perform tournament selection to pick ``elite_size`` scripts.
        Returns a list of selected (elite) Script objects.
        """
        selected: List[Script] = []
        indices = list(range(len(self.population)))

        for _ in range(self.elite_size):
            tournament = random.sample(indices, self.tournament_size)
            # Pick the individual with highest fitness in the tournament
            best_idx = max(tournament, key=lambda i: fitness[i])
            selected.append(self.population[best_idx].copy())

        return selected

    # ------------------------------------------------------------------
    # 4️⃣  Crossover (single‑point) --------------------------------------------
    def breed(self, parent_a: Script, parent_b: Script) -> Script:
        """
        Produce a child by single‑point crossover of two parents.
        The crossover point is chosen uniformly at random.
        """
        if len(parent_a) != len(parent_b):
            raise ValueError("Parents must have the same rule length")

        point = random.randint(1, len(parent_a) - 1)
        child_rules = parent_a.rules[:point] + parent_b.rules[point:]
        return Script(child_rules)

    # ------------------------------------------------------------------
    # 5️⃣  Mutation ------------------------------------------------------------
    def mutate(self, script: Script) -> Script:
        """
        Mutate a script in‑place with probability ``mutation_rate`` per rule.
        Each mutated rule is replaced by a new random integer in the allowed range.
        """
        low, high = self.rule_range
        mutated = script.copy()
        for i in range(len(mutated.rules)):
            if random.random() < self.mutation_rate:
                mutated.rules[i] = random.randint(low, high)
        return mutated

    # ------------------------------------------------------------------
    # 6️⃣  One generation -------------------------------------------------------
    def evolve_one_generation(self, scenarios: List[Any], gpu: bool = True) -> None:
        """
        Execute a full generation:
        * evaluate → select → breed → mutate → replace worst
        * store statistics in ``self.history``
        """
        # ---- evaluate -------------------------------------------------------
        fitness = self.evaluate(scenarios, gpu=gpu)

        # ---- statistics -----------------------------------------------------
        avg_fit = float(np.mean(fitness))
        best_fit = float(np.max(fitness))
        worst_fit = float(np.min(fitness))
        self.history.append(
            {"generation": self.generation, "avg": avg_fit, "best": best_fit, "worst": worst_fit}
        )

        # ---- select elite ----------------------------------------------------
        elite = self.select(fitness)

        # ---- breed children -------------------------------------------------
        children: List[Script] = []
        while len(children) < self.population_size - self.elite_size:
            parent_a, parent_b = random.sample(elite, 2)
            child = self.breed(parent_a, parent_b)
            child = self.mutate(child)
            children.append(child)

        # ---- replace worst performers ----------------------------------------
        # Sort current population by fitness (ascending) and keep the best elite
        sorted_by_fit = sorted(zip(self.population, fitness), key=lambda x: x[1], reverse=True)
        survivors = [s for s, _ in sorted_by_fit[: self.elite_size]]
        self.population = survivors + children

        self.generation += 1

    # ------------------------------------------------------------------
    # 7️⃣  Main evolution loop -------------------------------------------------
    def evolve(
        self,
        num_generations: int = 100,
        scenarios_per_gen: int = 10,
        adaptive: bool = True,
        gpu: bool = True,
        verbose: bool = True,
    ) -> None:
        """
        Run the evolutionary process.

        Parameters
        ----------
        num_generations : int
            Number of generations to evolve.
        scenarios_per_gen : int
            Number of scenarios used each generation.
        adaptive : bool
            If True, generate harder scenarios as fitness improves
            (via ``llm_generate_harder_scenarios`` placeholder).
        gpu : bool
            Attempt to use GPU if available.
        verbose : bool
            Print progress each generation.
        """
        # Ensure population exists
        if not self.population:
            self.initialize()

        for gen in range(num_generations):
            # ------------------------------------------------------------------
            # Scenario generation – static or adaptive
            # ------------------------------------------------------------------
            if adaptive and gen > 0:
                # Use the best scripts from the previous generation to ask the LLM
                # for harder scenarios.  This is a stub – replace with your own LLM call.
                best_scripts = self.get_best_scripts(n=self.elite_size)
                scenarios = self.llm_generate_harder_scenarios(best_scripts, scenarios_per_gen)
            else:
                scenarios = self.generate_scenarios(scenarios_per_gen)

            # ------------------------------------------------------------------
            # Run one generation
            # ------------------------------------------------------------------
            self.evolve_one_generation(scenarios, gpu=gpu)

            # ------------------------------------------------------------------
            # Optional LLM review after each generation (placeholder)
            # ------------------------------------------------------------------
            if adaptive:
                best_scripts = self.get_best_scripts(n=self.elite_size)
                self.llm_review(best_scripts)   # does nothing by default

            # ------------------------------------------------------------------
            # Progress output
            # ------------------------------------------------------------------
            if verbose:
                stats = self.history[-1]
                print(
                    f"Gen {stats['generation']:3d} | "
                    f"Best {stats['best']:.3f} | "
                    f"Avg {stats['avg']:.3f} | "
                    f"Worst {stats['worst']:.3f}"
                )

    # ------------------------------------------------------------------
    # 8️⃣  Helper – get top N scripts -----------------------------------------
    def get_best_scripts(self, n: int = 10) -> List[Script]:
        """Return the *n* scripts with highest average fitness on the last
        evaluated batch (or on a fresh random batch if none yet)."""
        if not self.history:
            # No history yet – evaluate on a fresh batch
            scenarios = self.generate_scenarios(5)
            fitness = self.evaluate(scenarios, gpu=False)
        else:
            # Re‑use the fitness from the most recent generation
            fitness = self.evaluate(self.generate_scenarios(5), gpu=False)

        sorted_indices = np.argsort(fitness)[::-1]
        return [self.population[i].copy() for i in sorted_indices[:n]]

    # ------------------------------------------------------------------
    # 9️⃣  Statistics ---------------------------------------------------------
    def get_statistics(self) -> Dict[str, Any]:
        """Return a dictionary with fitness history, convergence rate and
        a simple diversity metric (average Hamming distance between rule vectors)."""
        if not self.history:
            return {}

        # Convergence rate: slope of best fitness over last 10 generations
        recent = self.history[-10:] if len(self.history) >= 10 else self.history
        generations = np.array([h["generation"] for h in recent])
        best_vals = np.array([h["best"] for h in recent])
        if len(generations) > 1:
            # Linear regression slope
            slope = np.polyfit(generations, best_vals, 1)[0]
        else:
            slope = 0.0

        # Diversity: average pairwise Hamming distance
        def hamming(a: List[int], b: List[int]) -> float:
            return sum(x != y for x, y in zip(a, b)) / len(a)

        distances = []
        for i in range(len(self.population)):
            for j in range(i + 1, len(self.population)):
                distances.append(hamming(self.population[i].rules, self.population[j].rules))
        diversity = float(np.mean(distances)) if distances else 0.0

        return {
            "history": self.history,
            "convergence_slope": slope,
            "diversity": diversity,
        }

    # ------------------------------------------------------------------
    # 10️⃣  Export / Import ----------------------------------------------------
    def export_population(self, path: str) -> None:
        """Serialise the whole engine (population, generation, history) to ``path``."""
        data = {
            "population": self.population,
            "generation": self.generation,
            "history": self.history,
            "config": {
                "population_size": self.population_size,
                "elite_size": self.elite_size,
                "mutation_rate": self.mutation_rate,
                "tournament_size": self.tournament_size,
                "rule_length": self.rule_length,
                "rule_range": self.rule_range,
            },
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
        print(f"[INFO] Population exported to {path}")

    def import_population(self, path: str) -> None:
        """Load a previously exported engine state."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"No such file: {path}")
        with open(path, "rb") as f:
            data = pickle.load(f)

        self.population = data["population"]
        self.generation = data["generation"]
        self.history = data["history"]
        cfg = data["config"]
        self.population_size = cfg["population_size"]
        self.elite_size = cfg["elite_size"]
        self.mutation_rate = cfg["mutation_rate"]
        self.tournament_size = cfg["tournament_size"]
        self.rule_length = cfg["rule_length"]
        self.rule_range = cfg["rule_range"]
        print(f"[INFO] Population imported from {path}")

    # ------------------------------------------------------------------
    # 11️⃣  Scenario generation (stub) -----------------------------------------
    def generate_scenarios(self, n: int) -> List[Any]:
        """
        Produce ``n`` random scenarios.  Replace this stub with a real
        scenario generator that creates MUD‑Arena challenges.
        """
        low, high = self.rule_range
        # Simple placeholder: each scenario is a single integer target value
        return [random.randint(low, high) for _ in range(n)]

    # ------------------------------------------------------------------
    # 12️⃣  LLM hooks (place‑holders) -------------------------------------------
    def llm_review(self, best_scripts: List[Script]) -> None:
        """
        Hook for an LLM to analyse the best scripts and suggest rule
        improvements.  The default implementation does nothing – you can
        call an external API (OpenAI, Anthropic, etc.) here and then apply
        the suggestions to the population.
        """
        # Example (pseudo‑code):
        #   suggestions = call_llm_api(best_scripts)
        #   for script, suggestion in zip(best_scripts, suggestions):
        #       apply_suggestion(script, suggestion)
        pass

    def llm_generate_harder_scenarios(self, best_scripts: List[Script], n: int) -> List[Any]:
        """
        Hook for an LLM to create harder scenarios based on the current
        elite scripts.  Returns a list of scenario objects.
        """
        # Example (pseudo‑code):
        #   prompt = build_prompt(best_scripts)
        #   scenarios = call_llm_to_generate_scenarios(prompt, n)
        #   return scenarios
        # For now we just return a slightly tougher random batch:
        low, high = self.rule_range
        tougher_low = int(low + 0.2 * (high - low))
        return [random.randint(tougher_low, high) for _ in range(n)]


# ----------------------------------------------------------------------
# CLI -----------------------------------------------------------------
# ----------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evolution Engine for the MUD Arena – set it and watch the game go."
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=100,
        help="Number of generations to evolve (default: 100)",
    )
    parser.add_argument(
        "--population",
        type=int,
        default=200,
        help="Population size (default: 200)",
    )
    parser.add_argument(
        "--scenarios",
        type=int,
        default=20,
        help="Number of scenarios per generation (default: 20)",
    )
    parser.add_argument(
        "--elite",
        type=int,
        default=20,
        help="Number of elite scripts kept each generation (default: 20)",
    )
    parser.add_argument(
        "--mutation",
        type=float,
        default=0.1,
        help="Mutation probability per rule (default: 0.1)",
    )
    parser.add_argument(
        "--tournament",
        type=int,
        default=5,
        help="Tournament size for selection (default: 5)",
    )
    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="Enable adaptive scenario generation via LLM hooks",
    )
    parser.add_argument(
        "--no-gpu",
        action="store_true",
        help="Force CPU execution even if a GPU is available",
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        help="Path to export the final population (pickle)",
    )
    parser.add_argument(
        "--import",
        dest="import_path",
        type=str,
        default=None,
        help="Path to import a previously saved population",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Print per‑generation statistics",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    engine = EvolutionEngine(
        population_size=args.population,
        elite_size=args.elite,
        mutation_rate=args.mutation,
        tournament_size=args.tournament,
    )

    if args.import_path:
        engine.import_population(args.import_path)

    engine.evolve(
        num_generations=args.generations,
        scenarios_per_gen=args.scenarios,
        adaptive=args.adaptive,
        gpu=not args.no_gpu,
        verbose=args.verbose,
    )

    if args.export:
        engine.export_population(args.export)

    # Final summary
    stats = engine.get_statistics()
    print("\n=== Evolution Summary ===")
    print(f"Generations run: {engine.generation}")
    print(f"Best fitness ever: {stats['history'][-1]['best']:.3f}")
    print(f"Average diversity (Hamming): {stats['diversity']:.3f}")
    print(f"Convergence slope (best fitness): {stats['convergence_slope']:.4f}")


if __name__ == "__main__":
    # Allow the script to be imported without executing the CLI
    main()
```

### How to Use / Extend

| Step | What to replace / extend |
|------|--------------------------|
| **Script evaluation** | Implement the real MUD‑Arena simulation inside `Script.evaluate`. Return a numeric survival/score. |
| **Scenario generation** | Replace `generate_scenarios` with a function that builds proper arena maps, enemy configurations, etc. |
| **LLM review** | Fill `llm_review` with a call to your favourite LLM API (OpenAI, Anthropic, etc.) and apply the returned rule suggestions to the elite scripts. |
| **LLM scenario generation** | Fill `llm_generate_harder_scenarios` with a prompt that asks the LLM to craft tougher challenges based on the elite scripts. |
| **Rule representation** | If your scripts are more complex than a list of integers, adjust the `Script` class, the crossover (`breed`) and mutation (`mutate`) logic accordingly. |

The module is ready to run out‑of‑the‑box with the placeholder logic, and it provides clear extension points for the actual MUD‑Arena specifics and LLM integration. Happy evolving!