# Adversarial acceptance demos

Ba project minh họa dùng cùng `MutationTester`, không hard-code logic bài toán:

| Demo | Mục tiêu | Wrong solutions |
| --- | --- | --- |
| `FREQUENCY` | hit/miss, duplicate, most-frequent | always zero, presence-only, off-by-one |
| `RANGESUM` | point/whole/boundary, negative, overflow | always zero, exclude right endpoint, prefix-only |
| `GRAPH_TREE` | isolated vertex, path/tree, disconnected/cycle | always connected, `n-m`, ignore isolated |

Chạy bằng test tự động:

```bash
pytest -q tests/test_core.py -k adversarial_demos
```

Mỗi demo có `project.json`, reference `solution.py`, deterministic `generator.py`
và ba candidate `wrong_*.py`. Test chỉ thành công khi cả ba candidate bị giết và
mỗi counterexample có `reason.txt`.
