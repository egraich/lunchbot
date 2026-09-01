"""Unit tests for the board logic: name migration, reset, keyboard parsing."""

from bot.services.board import (
    STATUS_O,
    STATUS_O1,
    STATUS_X,
    build_keyboard,
    build_rows,
    parse_keyboard,
    toggle,
)

DATE = "2026-09-01"


def _rows():
    return build_rows(
        [(1, "Климович И"), (2, "Старик Ф"), (3, "Панько Н")],
        {2: STATUS_O},
        {3},
    )


def test_defaults_and_locked():
    rows = _rows()
    assert [r.status for r in rows] == [STATUS_X, STATUS_O, STATUS_X]
    assert not rows[0].locked and not rows[1].locked and rows[2].locked


def test_name_migrates_to_pressed_button():
    rows = toggle(_rows(), 1, "O1")
    line = build_keyboard(DATE, rows).inline_keyboard[1]
    assert [b.text for b in line] == ["❌", "Климович И 🍜", "✅"]


def test_name_migrates_to_right_button():
    rows = toggle(_rows(), 1, "O")
    line = build_keyboard(DATE, rows).inline_keyboard[1]
    assert [b.text for b in line] == ["❌", "🍜", "Климович И ✅"]


def test_second_click_resets_to_x():
    rows = toggle(toggle(_rows(), 1, "O1"), 1, "O1")
    line = build_keyboard(DATE, rows).inline_keyboard[1]
    assert line[0].text == "Климович И ❌"
    assert [b.text for b in line[1:]] == ["🍜", "✅"]


def test_locked_student_cannot_change():
    rows = toggle(_rows(), 3, "O")
    assert rows[2].status == STATUS_X


def test_roundtrip_build_parse():
    rows = toggle(_rows(), 1, "O")
    parsed = parse_keyboard(build_keyboard(DATE, rows))
    assert [(r.student_id, r.name, r.status, r.locked) for r in parsed] == [
        (r.student_id, r.name, r.status, r.locked) for r in rows
    ]


def test_locked_row_is_single_button():
    kb = build_keyboard(DATE, _rows())
    assert [b.text for b in kb.inline_keyboard[3]] == ["Панько Н ❌"]


def test_service_buttons():
    kb = build_keyboard(DATE, _rows())
    assert kb.inline_keyboard[0][0].text == "❌ НЕ ЗАПИСЫВАТЬ ❌"
    assert [b.text for b in kb.inline_keyboard[-1]] == ["🔄 Рестарт", "Подтвердить ✅"]


def test_arm_restart_keeps_selections():
    rows = toggle(_rows(), 1, "O")
    kb = build_keyboard(DATE, rows, arm="restart")
    assert [b.text for b in kb.inline_keyboard[-1]] == ["❓ Точно сбросить?", "Подтвердить ✅"]
    assert parse_keyboard(kb)[0].status == STATUS_O


def test_arm_confirm_empty():
    kb = build_keyboard(DATE, _rows(), arm="confirm")
    assert kb.inline_keyboard[-1][1].text == "✅ Точно записать пустым?"
    assert parse_keyboard(kb)[1].status == STATUS_O
