"""Kiểm thử các hàm trích xuất từ văn bản / infobox (dùng câu thật lấy từ Wikipedia tiếng Việt)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from collect_wikipedia import lead_text  # noqa: E402
from step3_integrate import (dissolution_from_text, founding_from_text, parse_count, parse_person,  # noqa: E402
                             province_from_name, province_from_text, province_near_place_words)


@pytest.fixture(scope="module")
def provs():
    p = ROOT / "data" / "silver" / "provinces.json"
    if not p.exists():
        pytest.skip("chưa chạy pipeline")
    return json.loads(p.read_text(encoding="utf-8"))


def name_of(provs, q):
    return provs[q]["name_vi"] if q else None


@pytest.mark.parametrize("text, year", [
    ("Viện Đại học Huế là một viện đại học công lập ở thành phố Huế, được thành lập vào năm 1957 dưới chính thể "
     "Việt Nam Cộng hoà.", 1957),
    ("Ngày thành lập: 26 tháng 12 năm 1955. Trụ sở chính: 229B, đường Bạch Đằng", 1955),
    ("Trường Đại học Tài chính - Kế toán … tồn tại từ năm 1976 đến năm 2001.", 1976),
    ("Năm 1995, học viện thành lập trên cơ sở tổ chức lại hệ thống đào tạo", 1995),
    ("Được đổi tên vào ngày 14 tháng 11 năm 2011 trên cơ sở nâng cấp", None),       # không có từ khoá thành lập
])
def test_founding_from_text(text, year):
    assert founding_from_text(text) == year


@pytest.mark.parametrize("text, year", [
    ("Năm 1975, dưới chính quyền mới, Viện Đại học Minh Đức bị giải thể.", 1975),
    ("Trường đã giải thể vào năm 2009 do hoạt động chồng chéo, không hiệu quả.", 2009),
    ("… tồn tại từ năm 1976 đến năm 2001.", 2001),
    ("Trường được thành lập năm 2002 trên cơ sở sáp nhập hai khoa.", None),
])
def test_dissolution_from_text(text, year):
    assert dissolution_from_text(text) == year


def test_lead_text_drops_image_captions():
    wikitext = ("[[Tập tin:Hue.jpg|nhỏ|phải|Vào thập niên 1920 đây là trụ sở của Viện Dân biểu]]\n"
                "'''Viện Đại học Huế''' là một viện đại học công lập, được thành lập vào năm 1957.\n== Lịch sử ==\n…")
    lead = lead_text(wikitext)
    assert "1920" not in lead and founding_from_text(lead) == 1957


def test_province_near_place_words(provs):
    t = "Học viện Kỹ thuật và Công nghệ an ninh đóng quân tại phường Thuận Thành, thành phố Bắc Ninh."
    assert name_of(provs, province_near_place_words(t, provs)) == "Bắc Ninh"
    t = "là một trường đại học quân sự có trụ sở đặt tại thành phố Hồ Chí Minh, trực thuộc Binh chủng Công binh"
    assert name_of(provs, province_near_place_words(t, provs)) == "Thành phố Hồ Chí Minh"


def test_province_from_name_ignores_person_name(provs):
    assert province_from_name("Học viện Chính trị Quốc gia Hồ Chí Minh", provs) is None
    assert name_of(provs, province_from_name("Đại chủng viện Thánh Giuse Sài Gòn", provs)) == "Thành phố Hồ Chí Minh"
    assert name_of(provs, province_from_name("Trường Đại học Nội vụ Hà Nội", provs)) == "Hà Nội"


def test_province_aliases(provs):
    assert name_of(provs, province_from_text("Thừa Thiên Huế", provs)) == "Huế"
    assert name_of(provs, province_from_text("Bà Rịa – Vũng Tàu", provs)) == "Bà Rịa - Vũng Tàu"


@pytest.mark.parametrize("text, name, honor", [
    ("GS. TS. TTND. Lê Ngọc Thành", "Lê Ngọc Thành", "GS TS TTND"),
    ("PGS.TS Bùi Hữu Toàn - Phụ trách Ban Giám đốc Học viện", "Bùi Hữu Toàn", "PGS TS"),
    ("Tiến sĩ. Trư­ơng Mạnh Dũng", "Trương Mạnh Dũng", None),
    ("Hòa thượng Thích Thanh Quyết", "Thích Thanh Quyết", "Hòa thượng"),
    ("Không có", None, None),
])
def test_parse_person(text, name, honor):
    n, h = parse_person(text)
    assert n == name
    if honor:
        assert h == honor


@pytest.mark.parametrize("text, n", [("khoảng 30.000", 30000), ("Hơn 145.000 sinh viên", 145000),
                                     ("16 chương trình", None), ("3.012", 3012)])
def test_parse_count(text, n):
    assert parse_count(text) == n


@pytest.mark.parametrize("raw, clean", [
    ("Bộ Nông nghiệp và Môi trường", "Bộ Nông nghiệp và Môi trường"),      # tên Bộ chứa chữ "và" — không được cắt
    ("Bộ Tài chính và", "Bộ Tài chính"),
    ("Bộ Xây dựng của nước Cộng hòa xã hội chủ nghĩa Việt Nam", "Bộ Xây dựng"),
    ("Bộ Văn hóa", "Bộ Văn hóa, Thể thao và Du lịch"),                     # bị cắt ở dấu phẩy
    ("Bộ Công thương Việt Nam", "Bộ Công Thương"),
    ("23px Bộ Quốc phòng (Việt Nam)", "Bộ Quốc phòng"),
    ("Bộ Tư lệnh Tăng - Thiết giáp của Bộ Quốc phòng", "Bộ Tư lệnh Tăng - Thiết giáp của Bộ Quốc phòng"),  # không phải Bộ
])
def test_clean_org_name(raw, clean):
    from step3_integrate import clean_org_name
    assert clean_org_name(raw) == clean
