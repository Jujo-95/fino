"""Check tracked content and optionally reachable history without printing secrets."""
import argparse
import re
import subprocess
from pathlib import PurePosixPath

EMAIL = re.compile(rb"[A-Za-z0-9][A-Za-z0-9._%+\-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SAFE_DOMAINS = {b"example.com", b"example.org", b"example.net", b"users.noreply.github.com"}
SECRETS = {
    "private-key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "github-token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})",
    "google-key": rb"AIza[0-9A-Za-z_-]{30,}",
    "nvidia-key": rb"nvapi-[A-Za-z0-9_-]{25,}",
    "groq-key": rb"gsk_[A-Za-z0-9]{25,}",
    "aws-key": rb"(?:AKIA|ASIA)[A-Z0-9]{16}",
    "jwt": rb"eyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{20,}",
    "openai-key": rb"sk-(?:proj-)?[A-Za-z0-9_-]{35,}",
    "credential-url": rb"(?:postgres(?:ql)?|mysql|mongodb)://[^\s:/]+:[^\s@/]{8,}@",
}
PERSONAL = re.compile(rb"/(?:Users|home)/[A-Za-z0-9_.-]+/")
DEV_DIRS = {".cursor", ".agents", ".codex", ".claude", ".gemini", "skills"}
DEV_FILES = {"AGENT.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "SKILL.md", ".mcp.json"}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def private_path(path: str) -> bool:
    item = PurePosixPath(path)
    return bool(
        set(item.parts) & DEV_DIRS or item.name in DEV_FILES
        or path.startswith(("work/", "workspaces/", ".runtime/", ".lab/", ".github/instructions/"))
        or item.name.startswith(".env") and item.name != ".env.example"
        or item.suffix in {".pem", ".key", ".p12", ".pfx", ".duckdb", ".sqlite", ".sqlite3"}
        or path in {"docs/04-IMPLEMENTATION-PLAYBOOK.md", ".github/copilot-instructions.md"}
    )


def content_findings(data: bytes) -> set[str]:
    result = {name for name, pattern in SECRETS.items() if re.search(pattern, data)}
    if PERSONAL.search(data):
        result.add("personal-filesystem-path")
    for match in EMAIL.findall(data):
        domain = match.rsplit(b"@", 1)[1].lower()
        if domain not in SAFE_DOMAINS and not domain.endswith((b".invalid", b".example")):
            result.add("non-placeholder-email")
    return result


def inspect_tree(ref: str, seen: set[str]) -> list[str]:
    findings = []
    for entry in git("ls-tree", "-rz", ref).split(b"\0"):
        if not entry:
            continue
        meta, raw_path = entry.split(b"\t", 1)
        path = raw_path.decode("utf-8", "replace")
        if private_path(path):
            findings.append(f"{ref[:12]}:{path}: private-path")
        sha = meta.split()[2].decode()
        if sha in seen or meta.split()[1] != b"blob":
            continue
        seen.add(sha)
        for kind in sorted(content_findings(git("cat-file", "blob", sha))):
            findings.append(f"{ref[:12]}:{path}: {kind}")
    return findings


def audit(history: bool) -> list[str]:
    refs = git("rev-list", "--all").decode().splitlines() if history else [git("write-tree").decode().strip()]
    seen: set[str] = set()
    findings = [item for ref in refs for item in inspect_tree(ref, seen)]
    if history:
        for entry in git("log", "--all", "--format=%h%x09%ae%x09%ce").splitlines():
            commit, author, committer = entry.split(b"\t", 2)
            if content_findings(author + b" " + committer):
                findings.append(commit.decode() + ":commit-metadata: non-placeholder-email")
    return findings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="Include all reachable commits and authors.")
    args = parser.parse_args()
    issues = audit(args.history)
    for issue in issues:
        print(issue)
    print(f"Repository privacy check: {len(issues)} finding(s). Values are never printed.")
    raise SystemExit(bool(issues))
