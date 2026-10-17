from evallab.cache import DiskCache


def test_cache_roundtrip_and_corrupt(tmp_path):
    c = DiskCache(tmp_path / "c")
    k = c.key({"b": 1, "a": [1, 2]})
    assert k == c.key({"a": [1, 2], "b": 1}) and len(k) == 64
    assert c.get(k) is None
    c.put(k, {"x": 1})
    assert c.get(k) == {"x": 1} and c.has(k)
    (tmp_path / "c" / f"{k}.json").write_text("{broken")
    assert c.get(k) is None
