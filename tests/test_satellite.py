from pathlib import Path

from rasterreg.exceptions import SceneDiscoveryError
from rasterreg.satellite import process_satellite_batch


def test_batch_isolates_expected_scene_failure(monkeypatch, tmp_path) -> None:
    failed_scene = tmp_path / "failed"
    good_scene = tmp_path / "good"
    failed_scene.mkdir()
    good_scene.mkdir()

    successful_result = object()

    def fake_process(scene_directory, *args, **kwargs):
        scene = Path(scene_directory)
        if scene.name == "failed":
            raise SceneDiscoveryError("invalid test scene")
        return successful_result

    monkeypatch.setattr(
        "rasterreg.satellite.process_satellite_scene",
        fake_process,
    )

    results = process_satellite_batch(
        [failed_scene, good_scene],
        dem_path=None,
        output_root=tmp_path / "output",
    )

    assert len(results) == 2

    assert results[0].result is None
    assert results[0].error == "invalid test scene"

    assert results[1].result is successful_result
    assert results[1].error is None