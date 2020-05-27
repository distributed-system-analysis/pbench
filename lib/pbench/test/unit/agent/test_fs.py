from pathlib import Path

from pbench.agent import fs


def test_removetree(tmpdir):
    f1 = Path(tmpdir) / "foo"
    f1.mkdir()
    assert f1.exists()
    result = fs.removetree(tmpdir.strpath)
    assert result == 0
    assert f1.exists() is False

    f2 = Path(tmpdir) / "foo"
    f2.touch()
    assert f2.exists()
    result = fs.removetree(tmpdir.strpath)
    assert result == 0
    assert f2.exists() is False


def test_removetree_failed(tmpdir):
    f1 = Path(tmpdir) / "foo"

    result = fs.removetree(f1)
    assert result == 0


def test_removedir(tmpdir):
    f1 = Path(tmpdir) / "foo"
    f1.mkdir()
    assert f1.exists()
    fs.removedir(f1)
    assert f1.exists() is False


def test_removefile(tmpdir):
    f1 = Path(tmpdir) / "foo"
    f1.write_text("")
    assert f1.exists()
    fs.removefile(f1)
    assert f1.exists() is False


def test_copyfile(tmpdir):
    src = Path(tmpdir) / "bar"
    src.write_text("")
    dest = Path(tmpdir) / "foo"
    dest.write_text("")

    fs.copyfile(src, dest)
    assert dest.exists()
