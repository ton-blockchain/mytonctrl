import ast
from collections import defaultdict
from dataclasses import dataclass, field
import sys
from types import ModuleType

import pytest

from mytoncore.utils import get_package_resource_path


@pytest.fixture
def stats_class(monkeypatch):
    # The workload imports its separate Python 3.14 TON framework. Compile its
    # actual packaged Stats class alone so CI can exercise it on Python 3.8+.
    with get_package_resource_path("mytonctrl", "scripts/benchmark.py") as script:
        source = ast.parse(script.read_text(), filename=str(script))
        stats = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "Stats")
        window = next(
            node for node in source.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "AVG_WINDOW" for target in node.targets)
        )
        module = ModuleType("benchmark_stats_regression")
        module.__dict__.update(dataclass=dataclass, field=field, defaultdict=defaultdict)
        monkeypatch.setitem(sys.modules, module.__name__, module)
        isolated = ast.Module(body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            window, stats,
        ], type_ignores=[])
        exec(compile(ast.fix_missing_locations(isolated), str(script), "exec"), module.__dict__)
    return module.Stats


def summary(stats, capsys, shards=8):
    stats.print_new_seconds()
    capsys.readouterr()  # Discard progress lines; only assert the final report.
    stats.print_summary(expected_bps=50, expected_tps=20000, shards=shards)
    return capsys.readouterr().out


def test_high_tps_with_incomplete_shard_coverage_still_reports_results(stats_class, capsys):
    stats = stats_class()
    for second in range(100, 111):
        stats.record_block(second, 2500, 1)
    stats.record_block(111, 1, 1)  # The newest second is not yet reportable.

    output = summary(stats, capsys)

    assert "Warning: full-shard warmup was not observed; summarizing available workload data." in output
    assert "Increase --duration for a steadier measurement." in output
    assert "Duration:        11s" in output
    assert "Total blocks:    11" in output
    assert "Total txs:       27500" in output
    assert "Avg TPS:         2500.00  (12.5% of expected 20000)" in output
    assert "Traceback" not in output


def test_full_shard_warmup_preserves_existing_normal_summary(stats_class, capsys):
    stats = stats_class()
    for shard in range(8):
        stats.record_block(100, 1, shard)
        stats.record_block(101, 100, shard)
        stats.record_block(102, 200, shard)
    stats.record_block(103, 1, 0)

    output = summary(stats, capsys)

    assert output == (
        "\n===== Benchmark Summary =====\n"
        "Duration:        2s\n"
        "Total blocks:    16\n"
        "Total txs:       2400\n"
        "Avg blocks/s:    8.00  (16.0% of expected 50.0)\n"
        "Avg TPS:         1200.00  (6.0% of expected 20000)\n"
        "=============================\n"
    )


def test_partial_seconds_after_full_warmup_remain_in_normal_summary(stats_class, capsys):
    stats = stats_class()
    for shard in range(8):
        stats.record_block(100, 1, shard)
        stats.record_block(101, 250, shard)
    stats.record_block(102, 3000, 0)
    stats.record_block(103, 1, 0)

    output = summary(stats, capsys)

    assert "Warning:" not in output
    assert "Duration:        2s" in output
    assert "Total blocks:    9" in output
    assert "Total txs:       5000" in output
    assert "Avg TPS:         2500.00  (12.5% of expected 20000)" in output


def test_partial_fallback_discards_low_activity_prefix_and_retains_elapsed_gaps(stats_class, capsys):
    stats = stats_class()
    for second, count in ((100, 4), (101, 8), (103, 1000), (105, 2000), (106, 1)):
        stats.record_block(second, count, 0)

    output = summary(stats, capsys)

    assert "full-shard warmup was not observed" in output
    assert "Duration:        3s" in output
    assert "Total blocks:    2" in output
    assert "Total txs:       3000" in output
    assert "Avg TPS:         1000.00  (5.0% of expected 20000)" in output


@pytest.mark.parametrize("transactions", [0, 8])
def test_no_workload_after_warmup_has_actionable_message_without_summary(stats_class, capsys, transactions):
    stats = stats_class()
    for second in (100, 101, 102):
        stats.record_block(second, transactions, 0)

    output = summary(stats, capsys)

    assert output == "No meaningful workload data collected after warmup. Increase --duration and retry.\n"
    assert "Benchmark Summary" not in output


@pytest.mark.parametrize("newest_second_only", [False, True])
def test_no_complete_seconds_keeps_existing_no_data_message(stats_class, capsys, newest_second_only):
    stats = stats_class()
    if newest_second_only:
        stats.record_block(100, 2500, 0)

    assert summary(stats, capsys) == "No data collected.\n"
