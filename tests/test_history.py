"""Тесты фиксов: время в callback_data без двоеточия, сетка календаря."""

import calendar

from bot.handlers.common import MCB
from bot.services.board import MealCB


def test_time_arg_packs_without_colon():
    cb = MCB(action="time_set", arg="0740")
    assert MCB.unpack(cb.pack()) == cb


def test_meal_cb_packs_with_dash_date():
    cb = MealCB(date="2026-09-01", student_id=12, action="O1")
    assert MealCB.unpack(cb.pack()) == cb


def test_calendar_grid_monday_first_sunday_last():
    # сентябрь 2026: 1-е — вторник, понедельник должен уехать в паддинг
    weeks = calendar.monthcalendar(2026, 9)
    assert weeks[0] == [0, 1, 2, 3, 4, 5, 6]
    assert all(len(week) == 7 for week in weeks)
    # воскресенье всегда в крайнем правом столбце
    assert weeks[0][6] == 6
    assert weeks[1][6] == 13
