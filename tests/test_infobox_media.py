"""Kiểm thử phần trích xuất infobox mở rộng: tên tham số tiếng Anh, tệp ảnh, mục Lịch sử, liên kết đối tác."""
import sys
from pathlib import Path

import mwparserfromhell as mw
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from collect_wikipedia import history_text, image_files, page_links, parse_infobox  # noqa: E402
from step3_integrate import media_of, normalize_infobox, parse_person  # noqa: E402

# Rút gọn từ bài "Trường Đại học VinUni" (bản mẫu tham số tiếng Anh)
VINUNI = """{{Thông tin trường đại học
| name = Trường Đại học VinUni
| image = Trường Đại học VinUni logo.png
| other_name = VinUniversity
| established = {{Start date and age|2019|12|17}}
| parent = [[Tập đoàn Vingroup]]
| affiliation = [[Đại học Cornell]]{{·}}[[Đại học Pennsylvania]]
| chairman = Lê Mai Lan
| principal = Tan Yap-Peng
}}
'''Trường Đại học VinUni''' là một trường đại học tư thục.

== Lịch sử hình thành ==
Tháng 11 năm 2017, Vingroup bắt đầu hợp tác với [[Đại học Cornell]] để khảo sát khả năng thành lập trường.<ref>x</ref>

[[Tập tin:VinUni campus.jpg|nhỏ|Khuôn viên]]
Ngày 17 tháng 12 năm 2019, Thủ tướng Chính phủ ký quyết định thành lập Trường Đại học VinUni.

== Tham khảo ==
{{tham khảo}}
"""


def test_english_infobox_params_are_mapped():
    _, box, _, links, files = parse_infobox(VINUNI)
    box = normalize_infobox(box)
    assert box["tên khác"] == "VinUniversity"
    assert box["ngày thành lập"].startswith("2019-12-17")
    assert box["hiệu trưởng"] == "Tan Yap-Peng"
    assert box["chủ tịch hội đồng trường"] == "Lê Mai Lan"
    assert normalize_infobox(links)["liên kết"] == ["Đại học Cornell", "Đại học Pennsylvania"]
    assert normalize_infobox(links)["tổ chức mẹ"] == ["Tập đoàn Vingroup"]
    assert files == ["Trường Đại học VinUni logo.png"]


def test_vietnamese_param_wins_over_alias():
    assert normalize_infobox({"principal": "A B", "hiệu trưởng": "Lê Văn C"})["hiệu trưởng"] == "Lê Văn C"


def test_history_section_is_plain_text_without_refs_or_images():
    h = history_text(VINUNI)
    paras = h.split("\n\n")
    assert len(paras) == 2
    assert paras[0].startswith("Tháng 11 năm 2017") and "<ref>" not in h and "Tập tin" not in h
    assert "Tham khảo" not in h


@pytest.mark.parametrize("raw, files", [
    ("Logo HUST.svg", ["Logo HUST.svg"]),
    ("[[Tập tin:Cổng trường.jpg|250px|Cổng chính]]", ["Cổng trường.jpg"]),
    ("[[File:A_b.png]]", ["A b.png"]),
    ("<!-- chưa có ảnh -->", []),
])
def test_image_files(raw, files):
    assert image_files(raw) == files


def test_page_links_skip_files_and_categories():
    code = mw.parse("[[Đại học Cornell|Cornell]], [[Tập tin:X.png]], [[Thể loại:Y]], [[en:Z]]")
    assert page_links(code) == ["Đại học Cornell"]


@pytest.mark.parametrize("text, name", [("Tan Yap-Peng", "Tan Yap-Peng"), ("GS. TS. Jean-Pierre Dupont", "Jean-Pierre Dupont")])
def test_parse_person_hyphenated_names(text, name):
    assert parse_person(text)[0] == name


def test_media_prefers_existing_files_and_splits_logo_from_photo():
    images = {"Logo X.svg": {"url": "https://upload.wikimedia.org/a.svg", "thumb": "t", "page": "p", "license": "PD", "artist": ""},
              "Cổng X.jpg": {"url": "https://upload.wikimedia.org/b.jpg", "thumb": "t2", "page": "p2", "license": "CC BY-SA 4.0", "artist": "A"}}
    m = media_of({"files": ["Không tồn tại.png", "Logo X.svg", "Cổng X.jpg"]}, {}, images)
    assert m["logo"]["file"] == "Logo X.svg" and m["image"]["file"] == "Cổng X.jpg"
    assert media_of({"files": []}, {"image": ["Cổng X.jpg"]}, images)["image"]["license"] == "CC BY-SA 4.0"
