import pytest

from src.data.metric_schema import MetricContractError, load_all_contracts, load_contract


def test_load_real_contracts_from_repo():
    contracts = load_all_contracts("metrics")
    names = {c.name for c in contracts}
    assert names == {"conversion_rate", "revenue"}


def test_bad_direction_sign_for_higher_is_better():
    contracts = {c.name: c for c in load_all_contracts("metrics")}
    assert contracts["conversion_rate"].bad_direction_sign() == -1  # a fall is the bad direction


def test_missing_contract_file_raises(tmp_path):
    with pytest.raises(MetricContractError):
        load_contract(tmp_path / "does_not_exist.yaml")


def test_missing_required_field_raises(tmp_path):
    path = tmp_path / "contract.yaml"
    path.write_text("name: x\ndirection: higher_is_better\n", encoding="utf-8")
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_invalid_direction_raises(tmp_path):
    path = tmp_path / "contract.yaml"
    path.write_text(
        "name: x\ndirection: sideways\nbaseline_method: median_mad\n"
        "impact_method: direct_delta\ndimension: d\n"
        "severity:\n  watch: 2.0\n  high: 3.0\n",
        encoding="utf-8",
    )
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_invalid_impact_method_raises(tmp_path):
    path = tmp_path / "contract.yaml"
    path.write_text(
        "name: x\ndirection: higher_is_better\nbaseline_method: median_mad\n"
        "impact_method: made_up_method\ndimension: d\n"
        "severity:\n  watch: 2.0\n  high: 3.0\n",
        encoding="utf-8",
    )
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_high_threshold_below_watch_raises(tmp_path):
    path = tmp_path / "contract.yaml"
    path.write_text(
        "name: x\ndirection: higher_is_better\nbaseline_method: median_mad\n"
        "impact_method: direct_delta\ndimension: d\n"
        "severity:\n  watch: 3.0\n  high: 2.0\n",
        encoding="utf-8",
    )
    with pytest.raises(MetricContractError):
        load_contract(path)


def test_defaults_are_applied_when_optional_fields_omitted(tmp_path):
    path = tmp_path / "contract.yaml"
    path.write_text(
        "name: x\ndirection: higher_is_better\nbaseline_method: median_mad\n"
        "impact_method: direct_delta\ndimension: d\n"
        "severity:\n  watch: 2.0\n  high: 3.0\n",
        encoding="utf-8",
    )
    contract = load_contract(path)
    assert contract.window_days == 56
    assert contract.min_history_days == 14
    assert contract.min_volume_share == 0.0
    assert contract.sensitivity == 1.0
