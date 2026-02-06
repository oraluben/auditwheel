from pathlib import Path

import pytest

from auditwheel.architecture import Architecture
from auditwheel.lddtree import LIBPYTHON_RE, ldd, parse_ld_paths
from auditwheel.libc import Libc
from auditwheel.tools import zip2dir

HERE = Path(__file__).parent.resolve(strict=True)


@pytest.mark.parametrize(
    "soname",
    [
        "libpython3.7m.so.1.0",
        "libpython3.9.so.1.0",
        "libpython3.10.so.1.0",
        "libpython999.999.so.1.0",
    ],
)
def test_libpython_re_match(soname: str) -> None:
    assert LIBPYTHON_RE.match(soname)


@pytest.mark.parametrize(
    "soname",
    [
        "libpython3.7m.soa1.0",
        "libpython3.9.so.1a0",
    ],
)
def test_libpython_re_nomatch(soname: str) -> None:
    assert LIBPYTHON_RE.match(soname) is None


def test_libpython(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    wheel = (
        HERE / ".." / "integration" / "python_mscl-67.0.1.0-cp313-cp313-manylinux2014_aarch64.whl"
    )
    so = tmp_path / "python_mscl" / "_mscl.so"
    zip2dir(wheel, tmp_path)
    result = ldd(so)
    assert "Skip libpython3.13.so.1.0 resolution" in caplog.text
    assert result.interpreter is None
    assert result.libc == Libc.GLIBC
    assert result.platform.baseline_architecture == Architecture.aarch64
    assert result.platform.extended_architecture is None
    assert result.path is not None
    assert result.realpath.samefile(so)
    assert result.needed == (
        "libpython3.13.so.1.0",
        "libstdc++.so.6",
        "libm.so.6",
        "libgcc_s.so.1",
        "libc.so.6",
        "ld-linux-aarch64.so.1",
    )
    # libpython must be present in dependencies without path
    libpython = result.libraries["libpython3.13.so.1.0"]
    assert libpython.soname == "libpython3.13.so.1.0"
    assert libpython.path is None
    assert libpython.platform is None
    assert libpython.realpath is None
    assert libpython.needed == ()


class TestParseLdPaths:
    def test_nonexistent_path_filtered_by_default(self, tmp_path: Path) -> None:
        """Non-existent paths are filtered out by default."""
        nonexistent = str(tmp_path / "nonexistent")
        result = parse_ld_paths(nonexistent, path=str(tmp_path / "fake.so"))
        assert result == []

    def test_existing_path_kept_by_default(self, tmp_path: Path) -> None:
        """Existing paths are kept by default."""
        existing = tmp_path / "existing"
        existing.mkdir()
        result = parse_ld_paths(str(existing), path=str(tmp_path / "fake.so"))
        assert str(existing) in result

    def test_nonexistent_path_kept_when_keep_non_exist(self, tmp_path: Path) -> None:
        """Non-existent paths are kept when keep_non_exist=True."""
        nonexistent = str(tmp_path / "nonexistent")
        result = parse_ld_paths(
            nonexistent, path=str(tmp_path / "fake.so"), keep_non_exist=True
        )
        assert nonexistent in result

    def test_nonexistent_runpath_with_origin(self, tmp_path: Path) -> None:
        """$ORIGIN-based non-existent paths are preserved with keep_non_exist=True."""
        fake_so = tmp_path / "subdir" / "fake.so"
        fake_so.parent.mkdir(parents=True)
        fake_so.touch()
        result = parse_ld_paths(
            "$ORIGIN/nonexistent_lib",
            path=str(fake_so),
            keep_non_exist=True,
        )
        expected = str(fake_so.parent / "nonexistent_lib")
        assert expected in result

    def test_nonexistent_runpath_with_origin_filtered_by_default(
        self, tmp_path: Path
    ) -> None:
        """$ORIGIN-based non-existent paths are filtered by default."""
        fake_so = tmp_path / "subdir" / "fake.so"
        fake_so.parent.mkdir(parents=True)
        fake_so.touch()
        result = parse_ld_paths(
            "$ORIGIN/nonexistent_lib",
            path=str(fake_so),
        )
        assert result == []
