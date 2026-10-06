"""Skip list ordered index core.

An ordered index over int keys with search, ranked access, range scan and
in-order iteration; insert and delete keep the levels in shape.  Every
promotion decision comes from a source injected by the caller, so two lists
built from the same source end up with exactly the same levels.  The kernel
is pure in-memory arithmetic: no clock, no entropy source, no I/O.
"""

DEFAULT_PATTERN = (1, 0)


class SkipListError(Exception):
    """Raised when a skip list cannot carry out the requested operation."""


def _check_key(key):
    """Keys are plain ints; bool does not count as an int here."""
    if isinstance(key, bool) or not isinstance(key, int):
        raise TypeError("key must be an int")
    return key


class LevelSource:
    """A deterministic promotion source.

    The pattern is replayed cyclically, one decision per promotion check:
    True raises the level of the node being drawn, False stops it.  Two
    sources built from the same pattern hand out the same decisions, which
    keeps the whole kernel reproducible.
    """

    def __init__(self, pattern=DEFAULT_PATTERN):
        bits = []
        for bit in pattern:
            bits.append(1 if bit else 0)
        if not bits:
            raise ValueError("pattern must hold at least one decision")
        self.pattern = tuple(bits)
        self._cursor = 0

    @property
    def taken(self):
        """How many decisions the source has handed out so far."""
        return self._cursor

    def promote(self):
        """The next decision: True to raise a level, False to stop."""
        bit = self.pattern[self._cursor % len(self.pattern)]
        if bit:
            self._cursor += 1
        return bit == 1

    def reset(self):
        """Put the cursor back at the front of the pattern."""
        self._cursor = 0


class _Node:
    """One list node: a key, a value and one forward pointer per level."""

    __slots__ = ("key", "value", "forward")

    def __init__(self, key, value, level):
        self.key = key
        self.value = value
        self.forward = [None] * level

    @property
    def level(self):
        """How many forward pointers this node carries."""
        return len(self.forward)


class SkipList:
    """An ordered index over int keys, backed by a skip list.

    The header carries max_level forward pointers; the height of the list is
    the number of levels currently in use.  A node of level L appears on
    levels 0 to L - 1, and level 0 chains every node in ascending key order.
    """

    def __init__(self, source=None, max_level=8):
        if isinstance(max_level, bool) or not isinstance(max_level, int):
            raise TypeError("max_level must be an int")
        if max_level < 1:
            raise ValueError("max_level must be positive")
        self.max_level = max_level
        if source is None:
            source = LevelSource()
        elif not hasattr(source, "promote"):
            source = LevelSource(source)
        self.source = source
        self._head = _Node(None, None, max_level)
        self._level = 1
        self._size = 0

    # ---- shape ----

    def __len__(self):
        """How many keys are stored."""
        return self._size

    def __contains__(self, key):
        """Whether key is stored."""
        return self.contains(key)

    @property
    def height(self):
        """How many levels the list currently uses."""
        return self._level

    def node_levels(self):
        """The level of every node, in key order."""
        return [node.level for node in self._nodes()]

    def __iter__(self):
        """(key, value) pairs in ascending key order."""
        for node in self._nodes():
            yield node.key, node.value

    def items(self):
        """Every pair, in ascending key order."""
        return list(self)

    def keys(self):
        """Every key, ascending."""
        return [key for key, _ in self]

    def values(self):
        """Every value, in key order."""
        return [value for _, value in self]

    def _nodes(self):
        """Every node of the level 0 chain, in key order."""
        node = self._head.forward[0]
        while node is not None:
            yield node
            node = node.forward[0]

    # ---- lookups ----

    def _locate(self, key):
        """The node just before key at level 0; the header when key is first."""
        node = self._head
        for level in range(self._level - 1, -1, -1):
            while node.forward[level] is not None and node.forward[level].key <= key:
                node = node.forward[level]
        return node

    def get(self, key, default=None):
        """The value stored under key, or default when key is absent."""
        key = _check_key(key)
        node = self._locate(key).forward[0]
        if node is not None and node.key == key:
            return node.value
        return default

    def contains(self, key):
        """Whether key is stored."""
        key = _check_key(key)
        node = self._locate(key).forward[0]
        return node is not None and node.key == key

    def select(self, rank):
        """The (key, value) pair at the given 1-based rank."""
        if isinstance(rank, bool) or not isinstance(rank, int):
            raise TypeError("rank must be an int")
        if rank < 1 or rank > self._size:
            raise IndexError("rank %r is outside the list" % (rank,))
        node = self._head.forward[0]
        remaining = rank
        while remaining > 0 and node.forward[0] is not None:
            node = node.forward[0]
            remaining -= 1
        return node.key, node.value

    def rank(self, key):
        """The 1-based position of key, or 0 when key is absent."""
        key = _check_key(key)
        node = self._head.forward[0]
        position = 0
        while node is not None and node.key < key:
            node = node.forward[0]
            position += 1
        if node is not None and node.key == key:
            return position
        return 0

    def range_scan(self, low, high):
        """Every (key, value) pair with low <= key <= high, ascending."""
        low = _check_key(low)
        high = _check_key(high)
        found = []
        node = self._locate(low).forward[0]
        while node is not None and node.key < high:
            found.append((node.key, node.value))
            node = node.forward[0]
        return found

    # ---- updates ----

    def _find_path(self, key):
        """The rightmost node before key on every level of the list.

        Entry i holds the last node that is still below key on level i, so
        the new node can be spliced in at every level it carries.
        """
        path = [self._head] * self._level
        node = self._head
        for level in range(self._level - 1, 0, -1):
            while node.forward[level] is not None and node.forward[level].key < key:
                node = node.forward[level]
            path[level] = node
        return path

    def _draw_level(self):
        """The level a new node gets, decided by the injected source."""
        level = 1
        while level < self.max_level - 1 and self.source.promote():
            level += 1
        return level

    def _shrink(self):
        """Give back the levels that no longer hold any node."""
        if self._level > 1 and self._head.forward[self._level - 1] is None:
            self._level -= 1

    def insert(self, key, value):
        """Store value under key; True when the key was not stored before."""
        key = _check_key(key)
        path = self._find_path(key)
        node = path[0].forward[0]
        if node is not None and node.key == key:
            return False
        level = self._draw_level()
        node = _Node(key, value, level)
        while len(path) < level:
            path.append(self._head)
        for index in range(level):
            node.forward[index] = path[index].forward[index]
            path[index].forward[index] = node
        if level > self._level:
            self._level = level
        self._size += 1
        return True

    def delete(self, key):
        """Remove key; True when it was stored."""
        key = _check_key(key)
        path = self._find_path(key)
        node = path[0].forward[0]
        if node is None or node.key != key:
            return False
        for index in range(node.level):
            path[index].forward[index] = node.forward[index]
        self._size -= 1
        self._shrink()
        return True
