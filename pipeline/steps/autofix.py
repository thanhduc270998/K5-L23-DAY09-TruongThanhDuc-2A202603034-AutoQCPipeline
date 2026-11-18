"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _is_remove_code(code: str) -> bool:
    return code.startswith("DUP_IMAGE_") or code in REMOVE_CODES


def _clip_yolo_box(orig: str):
    """Cắt box về [0, 1]. Trả về (action, new_line); action='drop_line' nếu box nằm hẳn ngoài ảnh."""
    try:
        cls_id, cx, cy, w, h = parse_yolo_line(orig)
    except ValueError:
        return "drop_line", None
    x1 = max(0.0, min(1.0, cx - w / 2))
    y1 = max(0.0, min(1.0, cy - h / 2))
    x2 = max(0.0, min(1.0, cx + w / 2))
    y2 = max(0.0, min(1.0, cy + h / 2))
    nw, nh = x2 - x1, y2 - y1
    if nw <= 1e-9 or nh <= 1e-9:
        return "drop_line", None
    if cx - w / 2 >= 0.0 and cy - h / 2 >= 0.0 and cx + w / 2 <= 1.0 and cy + h / 2 <= 1.0:
        return "noop", orig
    ncx, ncy = (x1 + x2) / 2, (y1 + y2) / 2
    return "clip_box", f"{cls_id} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"


def _fix_yaml_classes(ds, cfg) -> list[dict]:
    """Chuẩn hoá trường `names` trong data.yaml theo `cfg['classes']` mà vẫn giữ các khoá khác."""
    desired = dict(enumerate(cfg["classes"]))
    current = ds.yaml_names()
    if current == desired and ds.yaml_path.exists():
        return []
    data = {}
    if ds.yaml_path.exists():
        loaded = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    data["names"] = desired
    ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return [{
        "image": "data.yaml",
        "line": None,
        "action": "rename_classes",
        "before": str(current),
        "after": str(desired),
    }]


def fix(ds, issues, cfg):
    """Tự động sửa lỗi severity ERROR trực tiếp trên thư mục `ds` và trả về log thay đổi."""
    remove_stems: set[str] = set()
    missing_stems: set[str] = set()
    drop_by_file: dict[str, set[int]] = defaultdict(set)
    clip_by_file: dict[str, set[int]] = defaultdict(set)
    has_bad_class_name = False

    for iss in issues:
        if iss.severity != ERROR:
            continue
        if _is_remove_code(iss.code):
            remove_stems.add(iss.image)
        elif iss.code == "BAD_CLASS_NAME":
            has_bad_class_name = True
        elif iss.code == "MISSING_LABEL_FILE":
            missing_stems.add(iss.image)
        elif iss.code in DROP_CODES and iss.line is not None:
            drop_by_file[iss.image].add(iss.line)
        elif iss.code == "BOX_OUT_OF_IMAGE" and iss.line is not None:
            clip_by_file[iss.image].add(iss.line)

    fixes: list[dict] = []

    for stem in sorted(remove_stems):
        img_p = ds.image_path(stem)
        lbl_p = ds.label_path(stem)
        removed_names = []
        if img_p is not None and img_p.exists():
            removed_names.append(img_p.name)
            img_p.unlink()
        if lbl_p.exists():
            removed_names.append(lbl_p.name)
            lbl_p.unlink()
        ds._size_cache.pop(stem, None)
        if removed_names:
            fixes.append({
                "image": stem,
                "line": None,
                "action": "remove_image",
                "before": ", ".join(removed_names),
                "after": "(đã xoá ảnh và nhãn)",
            })

    if has_bad_class_name:
        fixes.extend(_fix_yaml_classes(ds, cfg))

    for stem in sorted(missing_stems - remove_stems):
        if not ds.label_path(stem).exists():
            fixes.append({
                "image": stem,
                "line": None,
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })

    for stem in sorted((set(drop_by_file) | set(clip_by_file)) - remove_stems):
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        raw_lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        drop_lines = drop_by_file[stem]
        clip_lines = clip_by_file[stem]
        kept_lines = []
        changed = False

        for line_no, orig in enumerate(raw_lines, 1):
            if line_no in drop_lines:
                changed = True
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "drop_line",
                    "before": orig,
                    "after": "(đã xoá dòng)",
                })
                continue
            if line_no in clip_lines:
                act, new_line = _clip_yolo_box(orig)
                if act == "drop_line":
                    changed = True
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": orig,
                        "after": "(đã xoá: box ngoài ảnh)",
                    })
                    continue
                if act == "clip_box":
                    changed = True
                    kept_lines.append(new_line)
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "clip_box",
                        "before": orig,
                        "after": new_line,
                    })
                    continue
            kept_lines.append(orig)

        if changed:
            lp.write_text("\n".join(kept_lines) + ("\n" if kept_lines else ""), encoding="utf-8")

    return fixes
