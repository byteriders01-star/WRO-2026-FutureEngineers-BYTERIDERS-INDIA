import pytest

from checkpoint import CheckpointManager, Pose, DEFAULT_SECTIONS


class TestCheckpointManager:
    @pytest.fixture
    def mgr(self):
        return CheckpointManager(look_ahead_distance=0.5)

    def test_initial_no_section(self, mgr):
        assert mgr.get_current_section() is None
        assert mgr.get_transition_count() == 0

    def test_first_update_sets_initial_section(self, mgr):
        mgr.update(Pose(0.1, 0.0))
        assert mgr.get_current_section() is not None
        assert mgr.get_current_section_id() == 1

    def test_section_transition_on_look_ahead(self, mgr):
        mgr.update(Pose(0.1, 0.0))
        assert mgr.get_current_section_id() == 1

        mgr.update(Pose(1.1, 0.0))
        assert mgr.get_current_section_id() == 2
        assert mgr.get_transition_count() == 1

    def test_all_sections_traversed_in_order(self, mgr):
        mgr.update(Pose(0.1, 0.0))
        assert mgr.get_current_section_id() == 1

        for section in DEFAULT_SECTIONS[1:]:
            wp = section.waypoints[-1]
            mgr.update(Pose(wp[0], wp[1]))

        assert mgr.get_lap_count() == 1
        assert mgr.get_current_section_id() == 1

    def test_lap_completed_resets_to_section_1(self, mgr):
        mgr.update(Pose(0.1, 0.0))

        for i in range(2, 9):
            section = DEFAULT_SECTIONS[i - 1]
            wp = section.waypoints[-1]
            mgr.update(Pose(wp[0], wp[1]))

        assert mgr.get_lap_count() == 1
        assert mgr.get_current_section_id() == 1

    def test_behavior_from_section(self, mgr):
        mgr.update(Pose(0.1, 0.0))
        assert mgr.get_current_behavior() == "fast"

        mgr.update(Pose(1.1, 0.0))
        assert mgr.get_current_behavior() == "cornering"

    def test_initial_section_saved_in_history(self, mgr):
        mgr.update(Pose(0.1, 0.0))
        assert mgr.get_section_history() == [1]

    def test_section_history_tracked(self, mgr):
        mgr.update(Pose(0.1, 0.0))
        mgr.update(Pose(1.1, 0.0))

        assert mgr.get_section_history() == [1, 2]

    def test_history_reset_after_lap(self, mgr):
        mgr.update(Pose(0.1, 0.0))

        for section in DEFAULT_SECTIONS[1:]:
            wp = section.waypoints[-1]
            mgr.update(Pose(wp[0], wp[1]))

        assert mgr.get_section_history() == [1]

    def test_is_on_last_section(self, mgr):
        mgr.update(Pose(0.1, 0.0))
        assert not mgr.is_on_last_section()

        for i in range(2, 8):
            section = DEFAULT_SECTIONS[i - 1]
            wp = section.waypoints[-1]
            mgr.update(Pose(wp[0], wp[1]))

        assert mgr.is_on_last_section()

    def test_lap_count_increments(self, mgr):
        mgr.update(Pose(0.1, 0.0))

        for i in range(2, 9):
            section = DEFAULT_SECTIONS[i - 1]
            wp = section.waypoints[-1]
            mgr.update(Pose(wp[0], wp[1]))

        assert mgr.get_lap_count() == 1

    def test_multiple_laps(self, mgr):
        for _ in range(3):
            mgr.update(Pose(0.1, 0.0))

            for i in range(2, 9):
                section = DEFAULT_SECTIONS[i - 1]
                wp = section.waypoints[-1]
                mgr.update(Pose(wp[0], wp[1]))

        assert mgr.get_lap_count() == 3

    def test_reset(self, mgr):
        mgr.update(Pose(0.1, 0.0))
        mgr.update(Pose(1.1, 0.0))

        mgr.reset()

        assert mgr.get_current_section() is None
        assert mgr.get_transition_count() == 0
        assert mgr.get_lap_count() == 0
        assert len(mgr.get_section_history()) == 0