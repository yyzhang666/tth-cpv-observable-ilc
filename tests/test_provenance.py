from pathlib import Path

from ilc_tth_cpv.provenance import atomic_write_json, sha256_file


def test_sha256_and_atomic_json(tmp_path: Path):
    source = tmp_path / "source.txt"
    source.write_text("observable\n")
    assert sha256_file(source) == "7073c52c8cae9566b9dc5ecd255165f8eda779fa6627248b68a15f20f397e081"

    output = tmp_path / "nested/manifest.json"
    atomic_write_json(output, {"status": "ok"})
    assert output.read_text() == '{\n  "status": "ok"\n}\n'
