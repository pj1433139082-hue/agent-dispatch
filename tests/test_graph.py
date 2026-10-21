from __future__ import annotations

from pathlib import Path

from agent_dispatch.graph import build_plan
from agent_dispatch.ticket import Ticket


def ticket(
    ticket_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    write_scope: tuple[str, ...] = ("src/agent_dispatch/graph.py",),
) -> Ticket:
    return Ticket(
        id=ticket_id,
        title=f"Ticket {ticket_id}",
        path=Path(f"{ticket_id}.md"),
        what_to_build="Do the thing.",
        owner="implementer",
        risk="L1",
        depends_on=depends_on,
        write_scope=write_scope,
    )


def test_independent_tickets_share_the_first_wave() -> None:
    plan = build_plan([ticket("B"), ticket("A"), ticket("C", depends_on=("A",))])

    assert plan.waves == [["A", "B"], ["C"]]
    assert plan.frontier == ["A", "B"]


def test_dependent_ticket_waits_for_every_blocker() -> None:
    plan = build_plan(
        [
            ticket("A"),
            ticket("B"),
            ticket("C", depends_on=("A", "B")),
        ]
    )

    assert plan.waves == [["A", "B"], ["C"]]


def test_cycle_is_excluded_and_reported() -> None:
    plan = build_plan(
        [
            ticket("A", depends_on=("B",)),
            ticket("B", depends_on=("A",)),
            ticket("C"),
        ]
    )

    assert plan.waves == [["C"]]
    assert sorted(plan.cycle) == ["A", "B"]
    assert any("cycle" in error for error in plan.errors)


def test_overlapping_write_scopes_conflict_within_a_wave() -> None:
    plan = build_plan(
        [
            ticket("A", write_scope=("src/agent_dispatch/graph.py",)),
            ticket("B", write_scope=("src/agent_dispatch/graph.py",)),
        ]
    )

    assert len(plan.conflicts) == 1
    conflict = plan.conflicts[0]
    assert {conflict.first, conflict.second} == {"A", "B"}
    assert conflict.scopes == ("src/agent_dispatch/graph.py",)


def test_disjoint_write_scopes_do_not_conflict() -> None:
    plan = build_plan(
        [
            ticket("A", write_scope=("src/agent_dispatch/graph.py",)),
            ticket("B", write_scope=("tests/test_graph.py",)),
        ]
    )

    assert plan.conflicts == []


def test_glob_scope_conflicts_with_a_file_inside_it() -> None:
    plan = build_plan(
        [
            ticket("A", write_scope=("src/agent_dispatch/**",)),
            ticket("B", write_scope=("src/agent_dispatch/graph.py",)),
        ]
    )

    assert len(plan.conflicts) == 1


def test_done_dependencies_are_satisfied() -> None:
    plan = build_plan(
        [ticket("A"), ticket("B", depends_on=("A",))],
        done={"A"},
    )

    assert plan.waves == [["B"]]
    assert plan.frontier == ["B"]
    assert plan.blocked == {}


def test_blocked_map_names_unfinished_dependencies() -> None:
    plan = build_plan([ticket("A"), ticket("B", depends_on=("A",))], done={"B"})

    # B is done, so A is simply unblocked; nothing is waiting.
    assert plan.blocked == {}


def test_blocked_ticket_is_not_in_frontier() -> None:
    plan = build_plan([ticket("A"), ticket("B", depends_on=("A",))])

    assert plan.frontier == ["A"]
    assert plan.blocked == {"B": ["A"]}
    assert "B" not in plan.waves[0]


def test_plan_is_deterministic_when_input_order_changes() -> None:
    first = build_plan([ticket("B"), ticket("A"), ticket("C", depends_on=("A",))])
    second = build_plan([ticket("C", depends_on=("A",)), ticket("A"), ticket("B")])

    assert first.to_dict() == second.to_dict()
