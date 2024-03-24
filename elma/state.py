from __future__ import annotations

import struct
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union, Iterator

from elma.constants import STATEDAT_SIZE
from elma.constants import STATEDAT_START
from elma.constants import STATEDAT_NUM_LEVELS
from elma.constants import STATEDAT_NUM_INTERNALS
from elma.constants import TOP10_SIZE
from elma.constants import STATEDAT_NUM_PLAYERS
from elma.constants import STATEDAT_PLAYER_STRUCT_SIZE
from elma.constants import STATEDAT_PLAYERENTRY_PADDING
from elma.constants import STATEDAT_PLAYERENTRY_NAME_SIZE
from elma.constants import STATEDAT_PLAYER_NAME_SIZE
from elma.constants import STATEDAT_LEVEL_NAME_SIZE
from elma.constants import STATEDAT_REGISTERED
from elma.constants import STATEDAT_SHAREWARE
from elma.models import Top10
from elma.utils import null_padded, format_time, internal_name, crypt_state, check_writable_file


__all__ = ["SoundOptimization", "PlayMode", "VideoDetail", "PlayerEntry", "PlayerKeys", "State"]


class SoundOptimization(Enum):
    Compatibility = 1
    BestQuality = 0


class PlayMode(Enum):
    Single = 1
    Multi = 0


class VideoDetail(Enum):
    Low = 0
    High = 1


class PlayerEntry(object):
    """
    Represents a player and their internal progress in the state.dat.

    Attributes:
        name (str): The name of the player (max 8 characters in practice).
        skipped_internals (list): True for the internals that have been skipped
            (list index = internal number - 1), False for the others.
        last_unlocked_internal (int): The last internal the player has reached
            (internal number - 1).
        selected_internal (int): The currently selected internal (internal number - 1),
            or -1 if an external level was selected last.
    """
    def __init__(self,
                 name: str = '',
                 skipped_internals: Optional[List[bool]] = None,
                 last_unlocked_internal: int = 0,
                 selected_internal: int = 0) -> None:
        if skipped_internals is None:
            skipped_internals = [False for _ in range(STATEDAT_NUM_INTERNALS)]
        self.name = name
        self.skipped_internals = skipped_internals
        self.last_unlocked_internal = last_unlocked_internal
        self.selected_internal = selected_internal

    def __repr__(self) -> str:
        return (
            'PlayerEntry(name: %s, skipped_internals: %s, last_unlocked_internal: %s, selected_internal: %s)' %
            (self.name, self.skipped_internals, self.last_unlocked_internal, self.selected_internal)
            )

    def __str__(self) -> str:
        skips = ', '.join([internal_name(i, True, '.')
                           for i in range(STATEDAT_NUM_INTERNALS)
                           if self.skipped_internals[i]]) if any(self.skipped_internals) else None
        selected_int = internal_name(self.selected_internal, True, '.')
        return (
            'PlayerEntry(name: %s, skipped internals: %s, last unlocked internal: %s, selected internal: %s)' %
            (self.name, skips, internal_name(self.last_unlocked_internal, True, '.'),
             selected_int if len(selected_int) > 0 else 'None')
             )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PlayerEntry):
            return NotImplemented
        return (self.name == other.name and
                self.skipped_internals == other.skipped_internals and
                self.last_unlocked_internal == other.last_unlocked_internal and
                self.selected_internal == other.selected_internal)

    def to_buffer(self) -> bytes:
        return b''.join([
            null_padded(self.name, STATEDAT_PLAYERENTRY_NAME_SIZE),
            bytes([int(i) for i in self.skipped_internals]),
            null_padded('', STATEDAT_PLAYERENTRY_PADDING),
            struct.pack('I', self.last_unlocked_internal),
            struct.pack('i', self.selected_internal)
        ])


class PlayerKeys(object):
    """
    Represents the keys for Player A or Player B in the state.dat.

    Attributes:
        throttle (int): Throttle key.
        brake (int): Brake key.
        rotate_right (int): Rotate right (= volt right) key.
        rotate_left (int): Rotate left (= volt left) key.
        change_direction (int): Change direction (= turn) key.
        toggle_navigator (int): Toggle the navigator (= minimap) on/off.
        toggle_timer (int): Toggle the timer on/off.
        toggle_show_hide (int): Show/hide your part of the split screen in multiplayer mode.
    """
    def __init__(self,
                 throttle: int,
                 brake: int,
                 rotate_right: int,
                 rotate_left: int,
                 change_direction: int,
                 toggle_navigator: int,
                 toggle_timer: int,
                 toggle_show_hide: int) -> None:
        self.throttle = throttle
        self.brake = brake
        self.rotate_right = rotate_right
        self.rotate_left = rotate_left
        self.change_direction = change_direction
        self.toggle_navigator = toggle_navigator
        self.toggle_timer = toggle_timer
        self.toggle_show_hide = toggle_show_hide

    def __repr__(self) -> str:
        return (
            '''PlayerKeys(throttle: %s, brake: %s, rotate_right: %s, rotate_left: %s,
            change_direction: %s, toggle_navigator: %s, toggle_timer: %s, toggle_show_hide: %s)''' %
            (self.throttle, self.brake, self.rotate_right, self.rotate_left,
             self.change_direction, self.toggle_navigator, self.toggle_timer, self.toggle_show_hide)
             )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PlayerKeys):
            return NotImplemented
        return (self.throttle == other.throttle and
                self.brake == other.brake and
                self.rotate_right == other.rotate_right and
                self.rotate_left == other.rotate_left and
                self.change_direction == other.change_direction and
                self.toggle_navigator == other.toggle_navigator and
                self.toggle_timer == other.toggle_timer and
                self.toggle_show_hide == other.toggle_show_hide)

    def to_buffer(self) -> bytes:
        return b''.join([
            struct.pack('I', self.throttle),
            struct.pack('I', self.brake),
            struct.pack('I', self.rotate_right),
            struct.pack('I', self.rotate_left),
            struct.pack('I', self.change_direction),
            struct.pack('I', self.toggle_navigator),
            struct.pack('I', self.toggle_timer),
            struct.pack('I', self.toggle_show_hide)
        ])


class State(object):
    """
    Represents an Elasto Mania state.dat file.

    Attributes:
        version (int): STATEDAT_VERSION
        times (list): A list of 90 Top10s (internal levels + empty slots).
        players (list): A list of PlayerEntry objects in the state.dat.
            Only player_count players are read, even though state.dat has
            a fixed number of 50 PlayerEntry slots.
        player_count (int): The number of players in the state.dat.
        player_A_name (str): The name of the currently selected player A.
        player_B_name (str): The name of the currently selected player B.
        sound_enabled (bool): Whether the sound effects are enabled or not.
        sound_optimization (SoundOptimization): Whether best sound quality
            or compatibility is preferred.
        play_mode (PlayMode): Whether Single or Multi mode is selected.
        flag_tag (bool): Whether Flag Tag mode is on or not.
        swap_bikes (bool): Whether the "101" bike is used for player A instead of
            the default "8" bike or not.
        video_detail (VideoDetail): Whether high details (grass, pictures,
            textures) are shown or not.
        animated_objects (bool): Whether the objects are animated or still.
        animated_menus (bool): Whether the menu background has moving discs or not.
        player_A_keys (PlayerKeys): Keys for player A.
        player_B_keys (PlayerKeys): Keys for player B.
        inc_screen_size_key (int): Key for increasing the screen size (border zoom).
        dec_screen_size_key (int): Key for decreasing the screen size (border zoom).
        screenshot_key (int): Key for taking a screenshot (snp#####.pcx).
        last_edited_lev_name (str): Name of the level last opened in the editor
            (including .lev extension).
        last_played_external (str): Name of the last played external level
            (including .lev extension).
        registered (int): STATEDAT_REGISTERED or STATEDAT_SHAREWARE
    """
    def __init__(self) -> None:
        self.version: int = STATEDAT_START
        self.times: List[Top10] = [Top10() for _ in range(STATEDAT_NUM_LEVELS)]
        self.players: List[PlayerEntry] = []
        self.player_count: int = 0
        self.player_A_name: str = ''
        self.player_B_name: str = ''
        self.sound_enabled: bool = True
        self.sound_optimization: SoundOptimization = SoundOptimization.BestQuality
        self.play_mode: PlayMode = PlayMode.Single
        self.flag_tag: bool = False
        self.swap_bikes: bool = False
        self.video_detail: VideoDetail = VideoDetail.High
        self.animated_objects: bool = True
        self.animated_menus: bool = True
        self.player_A_keys: PlayerKeys = PlayerKeys(200, 208, 205, 203, 57, 47, 20, 2)
        self.player_B_keys: PlayerKeys = PlayerKeys(76, 80, 81, 79, 82, 48, 21, 3)
        self.inc_screen_size_key: int = 13
        self.dec_screen_size_key: int = 12
        self.screenshot_key: int = 23
        self.last_edited_lev_name: str = ''
        self.last_played_external: str = ''
        self.registered: int = STATEDAT_REGISTERED

    def __repr__(self) -> str:
        return (
            '''
State(version: %s,
times: %s,
players: %s,
player_count: %s,
player_A_name: '%s',
player_B_name: '%s',
sound_enabled: %s,
sound_optimization: %s,
play_mode: %s,
flag_tag: %s,
swap_bikes: %s,
video_detail: %s,
animated_objects: %s,
animated_menus: %s,
player_A_keys: %s,
player_B_keys: %s,
inc_screen_size_key: %s,
dec_screen_size_key: %s,
screenshot_key: %s,
last_edited_lev_name: '%s',
last_played_external: '%s',
registered: %s)
''' %
            (self.version, self.times, self.players if self.player_count > 0 else None,
             self.player_count, self.player_A_name, self.player_B_name, self.sound_enabled,
             self.sound_optimization.name, self.play_mode.name, self.flag_tag, self.swap_bikes,
             self.video_detail.name, self.animated_objects, self.animated_menus, self.player_A_keys,
             self.player_B_keys, self.inc_screen_size_key, self.dec_screen_size_key,
             self.screenshot_key, self.last_edited_lev_name, self.last_played_external,
             'STATEDAT_REGISTERED' if self.registered == STATEDAT_REGISTERED else 'STATEDAT_SHAREWARE')
             )

    def __str__(self) -> str:
        return (
            '''
players: %s
player count: %s
total times: %s
player details: %s
''' %
            (', '.join([p.name for p in self.players if len(p.name) > 0]),
             self.player_count,
             ', '.join([f'{format_time(self.total_time(p.name))} {p.name}'
                        for p in self.players if len(p.name) > 0]),
             ', '.join([str(p) for p in self.players if len(p.name) > 0]))
             )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, State):
            return NotImplemented
        return (self.version == other.version and
                self.times == other.times and
                self.players == other.players and
                self.player_count == other.player_count and
                self.player_A_name == other.player_A_name and
                self.player_B_name == other.player_B_name and
                self.sound_enabled == other.sound_enabled and
                self.sound_optimization == other.sound_optimization and
                self.play_mode == other.play_mode and
                self.flag_tag == other.flag_tag and
                self.swap_bikes == other.swap_bikes and
                self.video_detail == other.video_detail and
                self.animated_objects == other.animated_objects and
                self.animated_menus == other.animated_menus and
                self.player_A_keys == other.player_A_keys and
                self.player_B_keys == other.player_B_keys and
                self.inc_screen_size_key == other.inc_screen_size_key and
                self.dec_screen_size_key == other.dec_screen_size_key and
                self.screenshot_key == other.screenshot_key and
                self.last_edited_lev_name == other.last_edited_lev_name and
                self.last_played_external == other.last_played_external and
                self.registered == other.registered)

    def save(self, file: Union[str, Path],
             allow_overwrite: bool = False,
             create_dirs: bool = False) -> None:
        """
        Save state.dat to a file

        Args:
            file: path to the file
            allow_overwrite: allow overwriting an existing file
            create_dirs: create non-existing parent directories of the file

        Raises:
            FileExistsError: if file exists and allow_overwrite = False
            FileNotFoundError: if parent directory of the file does not exist
                and create_dirs = False
        """
        file = Path(file)
        check_writable_file(file, exist_ok=allow_overwrite, create_dirs=create_dirs)
        file.write_bytes(self.pack())

    @classmethod
    def load(cls, file: Union[str, Path]) -> State:
        """
        Load state.dat from a file

        Args:
            file: path to a file containing an Elasto Mania state.dat

        Returns:
            State object unpacked from the file

        Raises:
            FileNotFoundError: if the file does not exist
        """
        file = Path(file)
        if not file.exists():
            raise FileNotFoundError(f"File {file} not found.")
        state = cls.unpack(file.read_bytes())
        return state

    def pack(self) -> bytes:
        """
        Pack state.dat to its binary representation readable by Elasto Mania

        Returns:
            Packed state.dat as bytes
        """
        packed_state = pack_state(self)
        return packed_state

    @classmethod
    def unpack(cls, packed_state: bytes) -> State:
        """
        Unpack state.dat from its binary representation readable by Elasto Mania

        Args:
            packed_state: packed state.dat as bytes

        Returns:
            Unpacked State object
        """
        state = unpack_state(packed_state)
        return state

    def total_time(self, player: Optional[str], combined: bool = False) -> int:
        """
        Return the total time of a player, or the anonymous total time.

        Args:
            player: name of the player, or None for the anonymous total time.
            combined: if true, combines single player and multiplayer times.

        Returns:
            Total time in hundredths of a second
        """
        tt = 0
        penalty = 60000  # +10 minutes for an unfinished level
        for i in range(STATEDAT_NUM_INTERNALS):
            pr = self.times[i].best_time(player)

            # over 10 minute PR still only counts as 10 minutes
            if pr is None or pr > penalty:
                pr = penalty

            if combined:
                pr_multi = self.times[i].best_time(player, False)
                if pr_multi is None or pr_multi > penalty:
                    pr_multi = penalty
                pr = min(pr, pr_multi)
            tt += pr
        return tt

    def stats_txt(self) -> str:
        """
        Create the same stats.txt that Elma (EOL) creates when closing.

        Returns:
            stats.txt contents (all top10s and total times) as a string.
        """
        top10s = ''
        for play_mode in ['Single player', 'Multiplayer']:
            top10s += f'\n\n{play_mode} times:\n'
            for i in range(STATEDAT_NUM_INTERNALS):
                top10_str = self.times[i].formatted_print(play_mode
                                                          == 'Single player', 4)
                spacer = '\n' if len(top10_str) > 0 else ''
                int_name = internal_name(i, True, ',')
                top10s += f'\nLevel {int_name}:\n{top10_str}{spacer}'

        tt = '\n'.join([f'{format_time(self.total_time(p.name)):<12}{p.name}'
                        for p in self.players if len(p.name) > 0])
        tt_combined = '\n'.join([f'{format_time(self.total_time(p.name, True)):<12}{p.name}'
                                 for p in self.players if len(p.name) > 0])
        tt_anonymous = f'{format_time(self.total_time(None))}'
        tt_anonymous_combined = f'{format_time(self.total_time(None, True))}'

        return f'''This text file is generated automatically each time you quit the
ELMA.EXE program. If you modify this file, you will loose the
changes next time you run the game. This is only an output file, the
best times are stored in the STATE.DAT binary file.
Registered version 1.3{top10s}
The following are the single player total times for individual players.
If a player doesn't have a time in the top ten for a level, this
will add ten minutes to the total time.
{tt}

The following are the combined total times for individual players. For each
level the best time is choosen of either the player's single player best
time, or the best multiplayer time where the player was one of the two
players.
If a player doesn't have such a time for a level, this will add ten
minutes to the total time.
{tt_combined}

The following is the anonymous total time of the best single player
times. If there is no single player time for a level, this will
add ten minutes to the total time.
{tt_anonymous}

The following is the anonymous combined total time of the best
single or multiplayer times. If there is no single or multiplayer
time for a level, this will add ten minutes to the total time.
{tt_anonymous_combined}

'''

    def rename_player(self, old_name: str, new_name: str) -> None:
        """
        Rename a player in the state.dat, top10 times included.

        Args:
            old_name: Name of the player to be renamed.
            new_name: New name for the player. Must not exist in self.players,
                but can exist in self.times.
        """
        assert (new_name not in [p.name for p in self.players])
        for p in self.players:
            if p.name == old_name:
                p.name = new_name
                break

        for top10 in self.times:
            for top10time in top10.single:
                if top10time.kuski == old_name:
                    top10time.kuski = new_name
                    top10time.kuski2 = new_name
            for top10time in top10.multi:
                if top10time.kuski == old_name:
                    top10time.kuski = new_name
                if top10time.kuski2 == old_name:
                    top10time.kuski2 = new_name

        if self.player_A_name == old_name:
            self.player_A_name = new_name
        if self.player_B_name == old_name:
            self.player_B_name = new_name


def pack_state(state: State) -> bytes:
    """
    Pack a state.dat to its binary representation readable by
    Elasto Mania.
    """
    players_and_dummies = state.players.copy()
    players_and_dummies.extend([PlayerEntry() for _ in
                                range(STATEDAT_NUM_PLAYERS - state.player_count)])
    state_data = [
        struct.pack('I', state.version)
    ] + [
        top10.to_buffer() for top10 in state.times[:STATEDAT_NUM_LEVELS]
    ] + [
        p.to_buffer() for p in players_and_dummies[:STATEDAT_NUM_PLAYERS]
    ] + [
        struct.pack('I', state.player_count),
        null_padded(state.player_A_name, STATEDAT_PLAYER_NAME_SIZE),
        null_padded(state.player_B_name, STATEDAT_PLAYER_NAME_SIZE),
        struct.pack('I', int(state.sound_enabled)),
        struct.pack('I', state.sound_optimization.value),
        struct.pack('I', state.play_mode.value),
        struct.pack('I', int(state.flag_tag)),
        struct.pack('I', int(not state.swap_bikes)),  # yes, it's inverted
        struct.pack('I', state.video_detail.value),
        struct.pack('I', int(state.animated_objects)),
        struct.pack('I', int(state.animated_menus)),
        state.player_A_keys.to_buffer(),
        state.player_B_keys.to_buffer(),
        struct.pack('I', state.inc_screen_size_key),
        struct.pack('I', state.dec_screen_size_key),
        struct.pack('I', state.screenshot_key),
        null_padded(state.last_edited_lev_name, STATEDAT_LEVEL_NAME_SIZE),
        null_padded(state.last_played_external, STATEDAT_LEVEL_NAME_SIZE),
        struct.pack('I', state.registered)
    ]
    return crypt_state(b''.join(state_data))


def unpack_state(packed_item: bytes) -> State:
    """
    Unpack a state.dat from its binary representation readable by
    Elasto Mania.
    """
    assert (len(packed_item) == STATEDAT_SIZE)
    data = iter(crypt_state(packed_item))

    def munch(n: int, dataiter: Iterator[int] = data) -> bytes:
        return b''.join([bytes(chr(next(dataiter)), 'latin1')
                         for _ in range(n)])

    state = State()
    state.version = struct.unpack('I', munch(4))[0]
    assert (state.version == STATEDAT_START)

    for i in range(STATEDAT_NUM_LEVELS):
        state.times[i].from_buffer(munch(TOP10_SIZE))

    player_iter = iter(munch(STATEDAT_NUM_PLAYERS * STATEDAT_PLAYER_STRUCT_SIZE))
    state.player_count = struct.unpack('I', munch(4))[0]
    assert (state.player_count <= STATEDAT_NUM_PLAYERS)

    for _ in range(state.player_count):
        name = munch(STATEDAT_PLAYERENTRY_NAME_SIZE,
                     player_iter).split(b'\0')[0].decode('latin1')
        skipped_internals = [struct.unpack('?', munch(1, player_iter))[0]
                             for _ in range(STATEDAT_NUM_INTERNALS)]
        munch(STATEDAT_PLAYERENTRY_PADDING, player_iter)
        last_unlocked_internal = struct.unpack('I', munch(4, player_iter))[0]
        selected_internal = struct.unpack('i', munch(4, player_iter))[0]
        state.players.append(PlayerEntry(name,
                                         skipped_internals,
                                         last_unlocked_internal,
                                         selected_internal))

    (
        state.player_A_name,
        state.player_B_name
    ) = [munch(STATEDAT_PLAYER_NAME_SIZE).split(b'\0')[0].decode('latin1')
         for _ in range(2)]

    state.sound_enabled = bool(struct.unpack('I', munch(4))[0])
    state.sound_optimization = SoundOptimization(struct.unpack('I', munch(4))[0])
    state.play_mode = PlayMode(struct.unpack('I', munch(4))[0])
    state.flag_tag = bool(struct.unpack('I', munch(4))[0])
    state.swap_bikes = not bool(struct.unpack('I', munch(4))[0])  # yes, it's inverted
    state.video_detail = VideoDetail(struct.unpack('I', munch(4))[0])
    state.animated_objects = bool(struct.unpack('I', munch(4))[0])
    state.animated_menus = bool(struct.unpack('I', munch(4))[0])

    '''
    throttle, brake, rotate_right, rotate_left,
    change_direction, toggle_navigator, toggle_timer, toggle_show_hide
    '''
    state.player_A_keys = PlayerKeys(*[struct.unpack('I', munch(4))[0]
                                       for _ in range(8)])
    state.player_B_keys = PlayerKeys(*[struct.unpack('I', munch(4))[0]
                                       for _ in range(8)])

    (
        state.inc_screen_size_key,
        state.dec_screen_size_key,
        state.screenshot_key
    ) = [struct.unpack('I', munch(4))[0] for _ in range(3)]

    (
        state.last_edited_lev_name,
        state.last_played_external
    ) = [munch(STATEDAT_LEVEL_NAME_SIZE).split(b'\0')[0].decode('latin1')
         for _ in range(2)]

    state.registered = struct.unpack('I', munch(4))[0]
    assert (state.registered in [STATEDAT_REGISTERED, STATEDAT_SHAREWARE])

    return state
