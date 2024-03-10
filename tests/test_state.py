from elma.state import SoundOptimization, PlayMode, VideoDetail, PlayerKeys, State
from elma.constants import STATEDAT_START
from elma.constants import STATEDAT_REGISTERED
from elma.utils import format_time
import unittest


class TestState(unittest.TestCase):

    def test_state_unpack(self):
        state = State.load('tests/files/state_snakeboa.dat')
        self.assertEqual(state.version, STATEDAT_START)
        self.assertEqual(state.player_count, 2)
        self.assertEqual(state.player_A_name, 'snake')
        self.assertEqual(state.player_B_name, 'boa')
        self.assertEqual(state.sound_enabled, False)
        self.assertEqual(state.sound_optimization, SoundOptimization.Compatibility)
        self.assertEqual(state.play_mode, PlayMode.Multi)
        self.assertEqual(state.flag_tag, True)
        self.assertEqual(state.swap_bikes, True)
        self.assertEqual(state.video_detail, VideoDetail.Low)
        self.assertEqual(state.animated_objects, False)
        self.assertEqual(state.animated_menus, False)
        self.assertEqual(state.player_A_keys, PlayerKeys(72, 76, 77, 75, 82, 71, 6, 3))
        self.assertEqual(state.player_B_keys, PlayerKeys(17, 31, 32, 30, 15, 46, 19, 2))
        self.assertEqual(state.inc_screen_size_key, 23)
        self.assertEqual(state.dec_screen_size_key, 24)
        self.assertEqual(state.screenshot_key, 25)
        self.assertEqual(state.last_edited_lev_name, '')
        self.assertEqual(state.last_played_external, 'zoo.lev')
        self.assertEqual(state.registered, STATEDAT_REGISTERED)

    def test_state_pack(self):
        state = State.load('tests/files/state_snakeboa.dat')
        state.flag_tag = not state.flag_tag
        state_repacked = state.unpack(state.pack())
        self.assertEqual(state, state_repacked)

    def test_new_state(self):
        state = State()
        self.assertEqual(state.animated_objects, True)
        self.assertEqual(state.player_A_keys, PlayerKeys(200, 208, 205, 203, 57, 47, 20, 2))

    def test_state_times(self):
        state = State.load('tests/files/state_snakeboa.dat')
        p1 = state.players[0]
        p2 = state.players[1]
        self.assertEqual(p1.name, 'snake')
        self.assertEqual(p1.skipped_internals[0:5], [False, True, True, False, False])
        self.assertEqual(p1.last_unlocked_internal, 3)
        self.assertEqual(p1.selected_internal, -1)
        self.assertEqual(p2.name, 'boa')
        self.assertEqual(p2.skipped_internals[0:5], [True, False, False, False, False])
        self.assertEqual(p2.last_unlocked_internal, 3)
        self.assertEqual(p2.selected_internal, 3)

        top10_int01 = state.times[0]
        top10_int02 = state.times[1]
        top10_int03 = state.times[2]
        self.assertEqual(top10_int01.single[0].time, 1453)
        self.assertEqual(top10_int01.single[0].kuski, 'snake')
        self.assertEqual(top10_int01.multi[0].time, 775)
        self.assertEqual(format_time(top10_int01.multi[0].time), '00:07:75')
        self.assertEqual(format_time(top10_int01.multi[0].time, False, '.'), '7.75')
        self.assertEqual(top10_int01.multi[1].time, 821)
        self.assertEqual(top10_int01.multi[1].kuski, 'snake')
        self.assertEqual(top10_int01.multi[1].kuski2, 'boa')
        self.assertEqual(top10_int02.single[0].time, 1737)
        self.assertEqual(top10_int02.single[0].kuski, 'boa')

        self.assertEqual(top10_int01.best_time('snake'), 1453)
        self.assertEqual(top10_int01.best_time(None), 1453)
        self.assertEqual(top10_int01.best_time('boa'), None)
        self.assertEqual(top10_int01.best_time('boa', False), 775)
        self.assertEqual(top10_int01.best_time(None, False), 775)
        self.assertEqual(top10_int02.best_time('snake'), None)
        self.assertEqual(top10_int03.best_time(None), 2050)

    def test_total_times(self):
        state = State.load('tests/files/state_snakeboa.dat')
        self.assertEqual(state.total_time('snake'), 3181453)
        self.assertEqual(state.total_time('boa'), 3123787)
        self.assertEqual(state.total_time('notfound'), 60000 * 54)
        self.assertEqual(format_time(state.total_time('snake')), '08:50:14:53')
        self.assertEqual(format_time(state.total_time('boa')), '08:40:37:87')
        self.assertEqual(format_time(state.total_time('snake', True)), '08:50:07:75')
        self.assertEqual(format_time(state.total_time('boa', True)), '08:30:45:62')
        self.assertEqual(format_time(state.total_time(None)), '08:30:52:40')
        self.assertEqual(format_time(state.total_time(None, True)), '08:30:45:62')

    def test_stats_txt(self):
        state = State.load('tests/files/state_snakeboa.dat')
        with open('tests/files/stats_snakeboa.txt', 'r') as eol_stats:
            self.assertEqual(state.stats_txt(), eol_stats.read())

    def test_rename_player(self):
        state = State.load('tests/files/state_snakeboa.dat')
        state.rename_player('snake', 'adder')
        self.assertEqual(state.players[0].name, 'adder')
        self.assertEqual(state.total_time('snake'), 60000 * 54)
        self.assertEqual(state.total_time('adder'), 3181453)
        self.assertEqual(state.times[0].best_time('adder'), 1453)
        self.assertEqual(state.times[0].multi[1].kuski, 'adder')
