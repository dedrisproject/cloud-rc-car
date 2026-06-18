from app import _parse_message


def test_bare_string_becomes_command():
    assert _parse_message("forward") == {"cmd": "forward"}


def test_json_command():
    assert _parse_message('{"cmd": "left"}') == {"cmd": "left"}


def test_json_ping():
    assert _parse_message('{"type": "ping", "t": 123}') == {"type": "ping", "t": 123}


def test_empty_is_none():
    assert _parse_message("") is None
    assert _parse_message("   ") is None


def test_invalid_json_is_none():
    assert _parse_message("{not json}") is None


def test_json_non_object_is_none():
    assert _parse_message("[1, 2, 3]") is None
