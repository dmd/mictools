from pathlib import Path
import studypar

testdir = Path(__file__).parent.parent / "tests" / "qc_mriqc"
yaml = Path(__file__).parent / "qctypes.yaml"


def test_studypar_files():
    s = studypar.Studypar(testdir / "studypar.Bergman.ss25m.THC-fMRI", yaml)
    m = s.info()
    assert m
    assert m["emails"] == ["ddrucker@mclean.harvard.edu"]
    assert m["folder"] == "THC"
    assert m["ident"] == "ss25m"

    s = studypar.Studypar(testdir / "studypar.Kohut.ss15f.CathinoneWinj", yaml)
    m = s.info()
    assert m
    assert m["emails"] == ["ddrucker@mclean.harvard.edu"]
    assert m["folder"] == "cathinone"
    assert m["ident"] == "ss15f"
