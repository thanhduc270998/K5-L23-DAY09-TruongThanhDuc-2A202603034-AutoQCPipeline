# Báo cáo Day 09 — <Họ và tên>, <MSHV>

> Xoá mọi `TODO(học viên)` và dòng gợi ý. Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
TODO(học viên): pipeline kết luận **Release / Hold / Rework**? Bao nhiêu ảnh vào, bao nhiêu ảnh ra dataset? Lý do chính (1–3 câu).

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| TODO(học viên) | | | |

TODO(học viên): vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy? Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa?

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 16 | DUP_IMAGE_NEAR 1.00 / 0.50 / 0.67 -> DUP_IMAGE_NEAR 1.00 / 0.83 / 0.91 | Giữ Precision 1.00 để tránh xóa nhầm ảnh sạch, tăng Recall bắt thêm ảnh gần trùng. Không tăng lên 20 vì dễ gộp nhầm sang tập test/val. |
| `second_opinion.conf` | 0.25 | 0.6 | WRONG_CLASS  0.56 / 0.83 / 0.67  MISSING      0.50 / 1.00 / 0.67  ->  WRONG_CLASS  0.62 / 0.83 / 0.71  MISSING      0.57 / 1.00 / 0.73 | Giữ được Recall cao để không bỏ sót lỗi thiếu nhãn/nhầm lớp (lên 0.7–0.8 sẽ sót), đồng thời tăng Precision để giảm báo động giả cho người duyệt (chấp nhận LOOSE_BOX giảm R 0.40→0.20). |

**một chỗ calibration có thể đánh lừa bạn** Bộ calib chỉ có 39 ảnh (mỗi loại lỗi chỉ có vài mẫu nên chỉ cần lệch 1 ảnh là Precision/Recall nhảy ~17–20%), và không có lỗi LEAK_TEST trong đáp án như dữ liệu thật. Cụ thể, phash_dist = 16 đạt Precision = 1.00 rất đẹp trên calib, nhưng khi đưa sang data/raw (224 ảnh) thì số ảnh bị loại ở bước 1 tăng lên 31 ảnh: riêng ở khoảng cách dist = 16, LEAK_TEST nhảy từ 5 lên 11 ảnh và DUP_IMAGE_NEAR từ 4 lên 7 ảnh, bắt nhầm cả những cặp khác nội dung nhãn như img_0011 (1 person) với img_0008 (2 person) hoặc img_0177 (person + bus) với img_0113 (person, ảnh vốn đã bị loại vì nhỏ). Vì vậy không nên tin tuyệt đối ngưỡng tối ưu trên calib mà cần kiểm tra lại trên raw.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
TODO(học viên): (a) chứng minh gate chặn đúng: chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên ảnh thiếu file nhãn còn nguyên), chỉ ra kết luận **Rework**, mã thoát 20 và việc **không xuất** dataset. (Đừng sửa tay `work/run/ds`: pipeline dựng lại thư mục này từ raw mỗi lần chạy.) (b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).

TODO(học viên): chênh mAP50 (clean − raw) so với **độ lệch chuẩn giữa các seed**; kết luận **trung thực** (nằm trong nhiễu thì nói là chưa kết luận được); ≥ 2 giả thuyết giải thích (ảnh trùng/rò rỉ test trong `raw`, nhãn máy còn lại trong `clean`, test chỉ 100 ảnh…) và cách kiểm.

## 6. Quyết định và ghi chú AI
- **(a) Quyết định cuối:** Pipeline kết luận **Hold** vì tuy không còn lỗi bắt buộc (`0` lỗi), nhưng sau khi duyệt hết ngân sách `80` ảnh thì vẫn còn `34/193` ảnh có cảnh báo chưa duyệt (`17.6% >= 10.0%`). Để chuyển thành **Release**, cần duyệt thêm ít nhất **15** ảnh cảnh báo nữa (nâng ngân sách lên khoảng `95` ảnh để kéo tỉ lệ xuống tối đa `19/193` ảnh, tức `< 10%`), không nâng ngưỡng quá cao để tránh bỏ sót lỗi thật.
- **(b) Ghi chú dùng AI:**
  - *Prompt chính:* Dán docstring và file test của từng module (`label_format`, `gate`, `autofix`, `second_opinion`), yêu cầu đọc ngưỡng từ `cfg`, giữ nguyên số dòng gốc khi có dòng trống/lỗi và không sửa `data/raw` hay `tests/`.
  - *Cách kiểm code AI:* Đọc lại code để chắc không hardcode ngưỡng hay `except: pass`, chạy `python -m pytest -q` qua đủ 79 test, rồi tự thử thêm mấy ca biên (1 dòng 2 lỗi, dòng hỏng trước `FALSE_POS`) và kiểm tra khi chạy thật trên `calib`/`raw`.
  - *Một lần AI sai/thừa:* Lúc mình chỉ bảo sửa 4 file code ở bước 2, AI lại chạy thêm `pipeline.run` làm sinh ra hàng loạt file trong `submission/` ngoài phạm vi; mình thấy file lạ hiện trên git nên đã yêu cầu xóa hết để giữ đúng 4 file.

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
