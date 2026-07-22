"""Display helpers for roadmap data.

The roadmap catalogue under data/roadmaps and data/roadmap_graphs was built by
scraping roadmap.sh, so it carries two recurring defects:

  1. Domain/topic labels were passed through str.title(), which destroys
     acronyms ("Ai Data Scientist", "Mlops", "Aws", "Sql").
  2. A handful of node/stage labels are scrape artifacts rather than real
     topics ("> >", "< <", "2", ") Predicting sales trends 2)...",
     "Machine Learning 6", "Shout out to Maria Vechtomova who", ...).

Rather than hand-editing ~150 JSON files, both problems are fixed here at read
time: display_name() rebuilds a correct label from the file stem, and is_junk()
/ clean_label() let every service drop or tidy artifact text before it reaches
the UI.
"""
import re

# Fully specified names for stems that no rule would capitalise correctly.
_SPECIAL = {
    "ai_agents": "AI Agents",
    "ai_data_scientist": "AI Data Scientist",
    "ai_engineer": "AI Engineer",
    "ai_red_teaming": "AI Red Teaming",
    "aspnet_core": "ASP.NET Core",
    "bi_analyst": "BI Analyst",
    "cpp": "C++",
    "cyber_security": "Cyber Security",
    "datastructures_and_algorithms": "Data Structures & Algorithms",
    "devops": "DevOps",
    "devops_beginner": "DevOps (Beginner)",
    "devrel": "DevRel",
    "devsecops": "DevSecOps",
    "git_github": "Git & GitHub",
    "ios": "iOS",
    "mlops": "MLOps",
    "mongodb": "MongoDB",
    "nextjs": "Next.js",
    "nodejs": "Node.js",
    "postgresql_dba": "PostgreSQL DBA",
    "server_side_game_developer": "Server-Side Game Developer",
    "shell_bash": "Shell & Bash",
    "software_design_architecture": "Software Design & Architecture",
    "spring_boot": "Spring Boot",
    "swift_ui": "SwiftUI",
    "ux_design": "UX Design",
}

# Whole words that should be upper-cased when they appear inside a stem.
_ACRONYMS = {
    "ai", "ml", "aws", "gcp", "css", "html", "sql", "php", "qa", "ui", "ux",
    "api", "dba", "bi", "nlp", "llm", "cli", "seo", "cdn", "sre",
}

# Whole words with fixed, non-title casing.
_WORD_FIX = {
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "github": "GitHub",
    "graphql": "GraphQL",
    "postgresql": "PostgreSQL",
    "cloudflare": "Cloudflare",
    "wordpress": "WordPress",
    "react": "React",
    "vue": "Vue",
}

_ALNUM = re.compile(r"[A-Za-z0-9]")

# Phrases that mark a scraped label as noise rather than a real learning topic.
# This also drops roadmap.sh's cross-navigation branches (e.g. "JavaScript
# Roadmap", "Find the interactive version of this", "more roadmaps at ...")
# which are links to OTHER roadmaps, not skills to learn on this one.
_JUNK_PATTERNS = re.compile(
    r"personal recommendation|alternative option|order not strict|learn anytime|"
    r"^visit\b|not required|pick this|along with|similar roadmap|beginner version|"
    r"opinion|shout ?out|linkedin profile|roadmap\.sh|^https?://|"
    r"\broadmaps?\s*$|find the (detailed|interactive)|interactive version|"
    r"more roadmaps|detailed version|other roadmaps|^click\b",
    re.I,
)


def display_name(stem: str) -> str:
    """Turn a roadmap file stem into a correctly capitalised display name."""
    key = (stem or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key in _SPECIAL:
        return _SPECIAL[key]
    words = []
    for w in key.split("_"):
        if not w:
            continue
        if w in _WORD_FIX:
            words.append(_WORD_FIX[w])
        elif w in _ACRONYMS:
            words.append(w.upper())
        else:
            words.append(w[:1].upper() + w[1:])
    return " ".join(words) or (stem or "")


def clean_label(text: str) -> str:
    """Tidy a scraped node/stage label (e.g. strip a trailing step number)."""
    t = (text or "").strip()
    t = re.sub(r"\s+\d{1,2}$", "", t).strip()  # "Machine Learning 6" -> "Machine Learning"
    return t


def is_junk(text: str) -> bool:
    """True when a label is a scrape artifact rather than a real topic."""
    t = (text or "").strip()
    if len(t) < 3:
        return True
    if not _ALNUM.match(t):          # starts with ")", ">", punctuation, etc.
        return True
    if "<" in t or ">" in t:
        return True
    if _JUNK_PATTERNS.search(t):
        return True
    return False
