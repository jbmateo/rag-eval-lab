import pytest

from evallab.experiments import ExperimentError, expand, experiment_git_state, load_experiment, run_id

GRID = """name: g
system: fake
dataset: drones@v1
grid: {quality: [0.3, 0.9], top_k: [4]}
"""


def test_grid_expansion_labels(write_experiment):
    exp, _ = load_experiment(write_experiment("g", GRID))
    assert expand(exp) == [("quality=0.3,top_k=4", {"quality": 0.3, "top_k": 4}),
                           ("quality=0.9,top_k=4", {"quality": 0.9, "top_k": 4})]


def test_variants_and_base(write_experiment):
    p = write_experiment("v", "name: v\nsystem: fake\ndataset: drones@v1\nbase: {top_k: 4}\n"
                              "variants:\n  - {label: a}\n  - {label: b, top_k: 2}\n")
    exp, text = load_experiment(p)
    assert expand(exp) == [("a", {"top_k": 4}), ("b", {"top_k": 2})] and text.startswith("name: v")
    single, _ = load_experiment(write_experiment("s", "name: s\nsystem: fake\ndataset: drones@v1\n"))
    assert expand(single) == [("base", {})]


def test_variant_needs_label(write_experiment):
    with pytest.raises(ExperimentError, match="label"):
        load_experiment(write_experiment("x", "name: x\nsystem: fake\ndataset: drones@v1\nvariants: [{top_k: 2}]\n"))


def test_grid_and_variants_exclusive(write_experiment):
    with pytest.raises(ExperimentError, match="grid"):
        load_experiment(write_experiment("x", GRID.replace("name: g", "name: x") + "variants: [{label: a}]\n"))


def test_llm_requires_hypothesis(write_experiment):
    with pytest.raises(ExperimentError, match="hypothesis"):
        load_experiment(write_experiment("h", "name: h\nsystem: fake\ndataset: drones@v1\nllm: true\n"))


def test_repeats_not_supported(write_experiment):
    with pytest.raises(ExperimentError, match="repeats"):
        load_experiment(write_experiment("r", GRID.replace("name: g", "name: r") + "repeats: 2\n"))


def test_git_state(write_experiment):
    p = write_experiment("g", GRID)
    sha, dirty = experiment_git_state(p)
    assert len(sha) == 40 and dirty is False
    p.write_text(GRID + "# edit\n")
    assert experiment_git_state(p)[1] is True
    new = write_experiment("n", GRID, commit=False)
    assert experiment_git_state(new) == ("", True)


def test_run_id_stable_and_sensitive():
    args = dict(dataset_sha="d", subset=None, lock_hash="l", system_version="s", judge_model="j",
                rubric_version="v1", config={"a": 1, "b": [1, 2]}, repeat=0)
    a = run_id(**args)
    assert a == run_id(**{**args, "config": {"b": [1, 2], "a": 1}}) and len(a) == 12
    assert a != run_id(**{**args, "config": {"a": 2, "b": [1, 2]}})
    assert a != run_id(**{**args, "system_version": "s2"})
    assert a != run_id(**{**args, "subset": "balanced-10"})
