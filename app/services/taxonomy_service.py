"""Hierarchical skill taxonomy with overlapping branches, implication and
alias support.

Node format in data/skill_taxonomy.json:
  "React": {"parents": [...], "children": [...], "implies": [...],
            "aliases": ["react", "reactjs", "react.js"]}

Aliases let free-text skill extraction recognise every surface form of a
skill (e.g. "py" or "python" both map to the canonical node "Python").
Replaces app/services/taxonomy_service.py.
"""
import json
import re
from pathlib import Path

TAXONOMY_PATH = Path("data/skill_taxonomy.json")


class TaxonomyService:
    def __init__(self):
        self.graph: dict = {}
        self._alias_index: dict = {}
        self.load()

    def load(self):
        if TAXONOMY_PATH.exists():
            self.graph = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        self._build_alias_index()

    def save(self):
        TAXONOMY_PATH.write_text(json.dumps(self.graph, indent=1), encoding="utf-8")
        self._build_alias_index()

    def _build_alias_index(self):
        self._alias_index = {}
        for name, node in self.graph.items():
            self._alias_index[name.lower()] = name
            for alias in node.get("aliases", []):
                self._alias_index[alias.lower()] = name

    def all(self) -> dict:
        return self.graph

    def upsert(self, name: str, node: dict):
        self.graph[name] = {
            "parents": node.get("parents", []),
            "children": node.get("children", []),
            "implies": node.get("implies", []),
            "aliases": node.get("aliases", []),
        }
        self.save()

    def delete(self, name: str):
        self.graph.pop(name, None)
        self.save()

    def canonical(self, skill: str) -> str:
        """Map any alias or casing to the canonical skill name."""
        return self._alias_index.get(skill.lower().strip(), skill)

    def expand(self, skills: list) -> set:
        """Expand a skill set with everything each skill implies, transitively.

        Knowing React implies knowing JavaScript, HTML and CSS.
        """
        result: set = set()
        stack = [self.canonical(s) for s in skills]
        while stack:
            s = stack.pop()
            if s in result:
                continue
            result.add(s)
            for imp in self.graph.get(s, {}).get("implies", []):
                if imp not in result:
                    stack.append(imp)
        return result

    def match_in_text(self, text: str) -> set:
        """Find every taxonomy skill mentioned in free text via aliases.

        Uses word-boundary matching so short aliases like "go" or "r" do not
        fire inside unrelated words. Single-letter and two-letter aliases are
        only matched when they appear as standalone tokens.
        """
        ALLOWED_SHORT = {"c#", "c++", "f#", "qa", "ui", "ux", "ai", "ml",
                         "bi", "s3", "2d", "3d", "k6", "c", "r", "go"}
        found: set = set()
        lower = text.lower()
        tokens = set(re.findall(r"[a-z0-9#+.]+", lower))
        for alias, canonical in self._alias_index.items():
            if len(alias) <= 2:
                if alias in ALLOWED_SHORT and alias in tokens:
                    found.add(canonical)
            elif re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", lower):
                found.add(canonical)
        return found


taxonomy_service = TaxonomyService()
