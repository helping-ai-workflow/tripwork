from scripts.transit import in_peak, walk_too_far

PEAKS = [{"label": "morning", "start": "07:30", "end": "09:30"},
         {"label": "evening", "start": "17:30", "end": "19:30"}]

def test_in_peak_inside_window():
    assert in_peak("08:00", PEAKS) is True

def test_in_peak_boundaries_inclusive():
    assert in_peak("07:30", PEAKS) is True
    assert in_peak("09:30", PEAKS) is True

def test_in_peak_outside_window():
    assert in_peak("07:29", PEAKS) is False
    assert in_peak("09:31", PEAKS) is False
    assert in_peak("12:00", PEAKS) is False

def test_in_peak_second_window():
    assert in_peak("18:00", PEAKS) is True

def test_in_peak_empty_windows():
    assert in_peak("08:00", []) is False

def test_walk_too_far_boundary():
    assert walk_too_far(15, 15) is False     # equal is OK
    assert walk_too_far(16, 15) is True

def test_walk_too_far_default_max():
    assert walk_too_far(20) is True          # default 15
    assert walk_too_far(10) is False

def test_walk_too_far_custom_max():
    assert walk_too_far(20, 25) is False
