"""Kiểm thử hợp đồng dữ liệu tầng silver: bản ghi hợp lệ được nhận, bản ghi sai bị chặn."""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from step3_integrate import validate_silver  # noqa: E402

GOOD = {
    "key": "Q3075696", "qid": "Q3075696", "name_vi": "Đại học Bách khoa Hà Nội", "name_en": "Hanoi University of Science and Technology",
    "kind": "University", "founding_year": 1956, "ownership": "public", "admission_codes": ["BKA"],
    "short_names": ["HUST"], "former_names": [], "ror": ["04jzsw495"], "website": "http://www.hust.edu.vn",
    "lat": 21.006, "long": 105.843, "province": "Q1858", "member_of": [], "branch_of": [], "governed_by": [],
    "owned_by": [], "leaders": [{"role": "director", "qid": "", "name": "Lê Anh Tuấn", "source": "viwiki"}],
}


def errors_for(**changes):
    rec = copy.deepcopy(GOOD)
    rec.update(changes)
    return [e["path"] + ": " + e["message"] for e in validate_silver({"institution": {rec["key"]: rec}})]


def test_valid_record_passes():
    assert errors_for() == []


def test_rejects_bad_values():
    assert errors_for(founding_year=1500)                       # ngoài khoảng năm
    assert errors_for(ownership="semi-public")                  # ngoài miền giá trị
    assert errors_for(admission_codes=["bka1"])                 # sai định dạng mã trường
    assert errors_for(lat=40.7)                                 # toạ độ ngoài lãnh thổ Việt Nam
    assert errors_for(kind="School")                            # loại hình không có trong ontology
    assert errors_for(qid="12345")                              # QID sai định dạng
    assert errors_for(leaders=[{"role": "rector", "name": "GS", "source": "viwiki"}])  # tên người 1 chữ
    assert errors_for(name_vi="")                               # thiếu tên tiếng Việt


def test_cross_field_rules():
    assert any("giải thể" in e for e in errors_for(founding_year=1990, dissolution_year=1975))
    assert any("không tồn tại" in e for e in errors_for(member_of=["Q999999999"]))
