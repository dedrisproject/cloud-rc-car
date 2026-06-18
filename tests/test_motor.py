import pytest

from config import Config
from motor import MotorController


@pytest.fixture
def motor():
    # mock_hardware -> serial writes are recorded in a list, no hardware needed.
    return MotorController(Config(mock_hardware=True))


def writes(motor):
    return motor._serial.writes


def test_unknown_command_raises(motor):
    with pytest.raises(ValueError):
        motor.handle("fly")


def test_command_to_serial_mapping(motor):
    motor.handle("forward")
    motor.handle("left")
    assert writes(motor) == ["7|", "14|"]


def test_dedup_same_channel(motor):
    motor.handle("forward")
    motor.handle("forward")  # duplicate -> skipped
    motor.handle("brake")
    assert writes(motor) == ["7|", "6|"]


def test_channels_are_independent(motor):
    # Holding forward + left steady must not repeat either command, but the two
    # channels must not dedup against each other.
    motor.handle("forward")  # 7
    motor.handle("left")     # 14
    motor.handle("forward")  # dup on drive channel -> skipped
    motor.handle("right")    # 15 (steer changed)
    motor.handle("brake")    # 6 (drive changed)
    assert writes(motor) == ["7|", "14|", "15|", "6|"]


def test_stop_forces_brake_and_center(motor):
    motor.handle("brake")    # 6
    motor.handle("center")   # 12
    motor.stop()             # forced 6 + 12 even though unchanged
    assert writes(motor) == ["6|", "12|", "6|", "12|"]


def test_state_reports_last_codes(motor):
    motor.handle("reverse")
    motor.handle("right")
    assert motor.state() == {"last_drive": "1", "last_steer": "15"}
