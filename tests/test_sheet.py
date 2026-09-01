"""Unit tests for the day-summary text for the class teacher."""

from bot.services.sheet import sheet_text


def test_sheet_counts_both_types():
    text = sheet_text("11-Б", {1: "O", 2: "O1", 3: "O"})
    assert text == "11-Б\n\nОбедов с I : 1\nОбедов без I : 2"


def test_sheet_empty_day():
    assert sheet_text("11-Б", {}) == "11-Б\n\nОбедов с I : 0\nОбедов без I : 0"


def test_sheet_format_is_copy_friendly():
    text = sheet_text("10-А", {7: "O1"})
    lines = text.splitlines()
    assert lines[0] == "10-А"
    assert lines[1] == ""
    assert lines[2] == "Обедов с I : 1"
    assert lines[3] == "Обедов без I : 0"
