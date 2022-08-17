import studypar

testdir = "tests/qc_mriqc"
yaml = "qc_mriqc/qctypes.yaml"


def test_studypar_files():
    s = studypar.Studypar(testdir + "/studypar.Bergman.ss25m.THC-fMRI", yaml)
    m = s.matches()
    assert m
    assert m["emails"] == ["ddrucker@mclean.harvard.edu"]
    assert m["folder"] == "THC"
    assert m["ident"] == "ss25m"

    s = studypar.Studypar(testdir + "/studypar.Kohut.ss15f.CathinoneWinj", yaml)
    m = s.matches()
    assert m
    assert m["emails"] == ["ddrucker@mclean.harvard.edu"]
    assert m["folder"] == "cathinone"
    assert m["ident"] == "ss15f"
