from forge.handlers.tickets import parse_plan_tasks

PLAN_SAMPLE = """# Foo Plan

**Goal:** build it

---

## Task 1: First thing

**Files:**
- Create: `a.py`

- [ ] Step 1: do a

## Task 2: Second thing

**Files:**
- Modify: `b.py`

- [ ] Step 1: do b

---

## Success Criteria
- something
"""


def test_parse_plan_tasks_returns_one_per_task_header():
    tasks = parse_plan_tasks(PLAN_SAMPLE)
    assert len(tasks) == 2
    assert tasks[0].number == 1
    assert tasks[0].title == "First thing"
    assert "do a" in tasks[0].body
    assert tasks[1].number == 2
    assert tasks[1].title == "Second thing"
    assert "do b" in tasks[1].body
    assert "do b" not in tasks[0].body


def test_parse_plan_tasks_empty_when_no_headers():
    assert parse_plan_tasks("# Nothing here\n\nJust text.") == []
