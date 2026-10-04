from pathlib import Path

from lifeagent.permissions import classify


def test_policy(tmp_path: Path):
    ws = tmp_path
    assert classify("Write", {"file_path": "notes/a.md"}, ws, False) == "allow"
    assert classify("Edit", {"file_path": str(ws / "memory/profile.md")}, ws, False) == "allow"
    assert classify("Write", {"file_path": "/etc/passwd"}, ws, False) == "deny"
    assert classify("Write", {"file_path": "../x"}, ws, False) == "deny"
    assert classify("Edit", {"file_path": ".claude/skills/x/SKILL.md"}, ws, False) == "ask"
    assert classify("Bash", {"command": "ls"}, ws, False) == "ask"
    assert classify("Bash", {"command": "ls"}, ws, True) == "allow"
    assert classify("mcp__google__search_gmail_messages", {}, ws, False) == "allow"
    assert classify("mcp__google__get_events", {}, ws, False) == "allow"
    assert classify("mcp__google__send_gmail_message", {}, ws, False) == "ask"
    assert classify("mcp__google__create_event", {}, ws, False) == "ask"
    assert classify("mcp__github__create_pull_request", {}, ws, False) == "ask"
    assert classify("mcp__github__list_pull_requests", {}, ws, False) == "allow"
    assert classify("SomethingNew", {}, ws, False) == "ask"
    assert classify("mcp__browser__browser_navigate", {}, ws, False) == "allow"
    assert classify("mcp__browser__browser_click", {}, ws, False) == "ask"


def test_trustable():
    from lifeagent.permissions import trustable

    assert trustable("Bash") and trustable("Write") and trustable("mcp__browser__browser_type")
    assert not trustable("mcp__google__send_gmail_message")
    assert not trustable("mcp__github__create_issue")
