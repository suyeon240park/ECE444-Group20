from app.services.cache import TTLCache


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_returns_what_was_stored():
    cache = TTLCache(60, clock=Clock())
    cache.set("a", "value")

    assert cache.get("a") == "value"
    assert cache.get("missing") is None


def test_entries_expire_after_the_ttl():
    clock = Clock()
    cache = TTLCache(60, clock=clock)
    cache.set("a", "value")

    clock.now += 59.9
    assert cache.get("a") == "value"
    clock.now += 0.1
    assert cache.get("a") is None


def test_setting_again_refreshes_the_ttl():
    clock = Clock()
    cache = TTLCache(60, clock=clock)
    cache.set("a", 1)
    clock.now += 50
    cache.set("a", 2)
    clock.now += 50

    assert cache.get("a") == 2


def test_oldest_entry_is_evicted_when_full():
    cache = TTLCache(60, max_entries=2, clock=Clock())
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_resetting_a_key_does_not_evict_others():
    cache = TTLCache(60, max_entries=2, clock=Clock())
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("b", 3)

    assert cache.get("a") == 1
    assert cache.get("b") == 3


def test_zero_ttl_disables_the_cache():
    cache = TTLCache(0, clock=Clock())
    cache.set("a", 1)

    assert not cache.enabled
    assert cache.get("a") is None


def test_zero_capacity_disables_the_cache():
    cache = TTLCache(60, max_entries=0, clock=Clock())
    cache.set("a", 1)

    assert not cache.enabled
    assert cache.get("a") is None
