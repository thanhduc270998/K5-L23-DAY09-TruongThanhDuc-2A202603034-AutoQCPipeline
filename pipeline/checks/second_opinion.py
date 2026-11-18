"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def _class_name(classes: list[str], cls_id: int) -> str:
    return classes[cls_id] if 0 <= cls_id < len(classes) else str(cls_id)


def _valid_label_lines(ds, stem: str):
    """Đọc các dòng nhãn hợp lệ kèm số dòng gốc (đếm từ 1); trả về None nếu thiếu file nhãn."""
    raw_lines = ds.read_label_lines(stem)
    if raw_lines is None:
        return None
    items = []
    n_classes = len(ds.classes)
    for line_no, raw in raw_lines:
        try:
            cls_id, cx, cy, w, h = parse_yolo_line(raw)
        except ValueError:
            continue
        if 0 <= cls_id < n_classes:
            items.append((line_no, cls_id, (cx, cy, w, h)))
    return items


def run(ds, cfg, preds=None):
    """Đối chiếu nhãn với dự đoán model `checker` để cảnh báo thiếu, lệch, sai lớp và thừa."""
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    so_cfg = cfg["second_opinion"]
    conf_thr = so_cfg["conf"]
    min_area_px = so_cfg["min_area_px"]
    fp_conf = so_cfg["fp_conf"]
    iou_missing = so_cfg["iou_missing"]
    iou_match = so_cfg["iou_match"]
    iou_loose = so_cfg["iou_loose"]

    issues = []
    for img_path in ds.image_files():
        stem = img_path.stem
        if stem not in preds:
            continue
        label_items = _valid_label_lines(ds, stem)
        if label_items is None:
            continue
        img_size = ds.image_size(stem)
        if img_size is None:
            continue

        img_w, img_h = img_size
        img_preds = preds[stem]

        for pred in img_preds:
            p_cls, p_conf, pcx, pcy, pw, ph = pred
            p_cls = int(p_cls)
            area_px = (pw * img_w) * (ph * img_h)
            if p_conf < conf_thr or area_px < min_area_px:
                continue

            p_box = (pcx, pcy, pw, ph)
            cands = []
            for _, l_cls, l_box in label_items:
                iou = iou_xywh(p_box, l_box)
                if iou >= iou_missing:
                    cands.append((l_cls, iou))

            pred_name = _class_name(ds.classes, p_cls)
            if not cands:
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_MISSING", stem,
                    f"model thấy {pred_name} (conf={p_conf:.2f}) nhưng nhãn không có box",
                    extra={"conf": round(float(p_conf), 4)},
                ))
                continue

            same_ious = [iou for l_cls, iou in cands if l_cls == p_cls]
            if same_ious:
                best_same = max(same_ious)
                if best_same < iou_loose:
                    issues.append(Issue(
                        "second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                        f"box {pred_name} lệch/lỏng (IoU={best_same:.2f} < {iou_loose})",
                        extra={"conf": round(float(p_conf), 4), "iou": round(best_same, 4)},
                    ))
            else:
                best_diff_cls, best_diff_iou = max(cands, key=lambda item: item[1])
                if best_diff_iou >= iou_match:
                    label_name = _class_name(ds.classes, best_diff_cls)
                    issues.append(Issue(
                        "second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                        f"nhãn ghi {label_name}, model dự đoán {pred_name} (conf={p_conf:.2f}, IoU={best_diff_iou:.2f})",
                        extra={"conf": round(float(p_conf), 4), "iou": round(best_diff_iou, 4)},
                    ))

        fp_boxes = [(pcx, pcy, pw, ph) for _, p_conf, pcx, pcy, pw, ph in img_preds if p_conf >= fp_conf]
        for line_no, l_cls, l_box in label_items:
            if all(iou_xywh(l_box, p_box) < iou_missing for p_box in fp_boxes):
                label_name = _class_name(ds.classes, l_cls)
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                    f"box nhãn {label_name} không khớp dự đoán nào (conf >= {fp_conf})",
                    line=line_no,
                ))

    return issues
