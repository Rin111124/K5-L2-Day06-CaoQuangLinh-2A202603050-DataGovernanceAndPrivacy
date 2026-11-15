# Báo cáo T05 — Phát hiện ảnh gần trùng và rò rỉ dữ liệu

**Trạng thái:** Toàn bộ cài đặt thuật toán (PoC & Baseline), kiểm thử tự động (pytest đạt 51 passed, 39 skipped) và quy trình Human-in-the-loop đã hoàn tất. Sinh viên đã thực hiện review đầy đủ 20 cặp biên trong hàng đợi review, áp dụng vào pipeline và ghi nhận nhật ký kiểm toán (AuditLog). Báo cáo phân tích chi tiết các failure mode (bẫy false merge đa scene, exact-hash leakage, và rò rỉ do biến đổi mạnh). Quyết định quản trị dữ liệu cuối cùng được xác lập là **HOLD** với mã lý do `T05_REVIEW_AND_GT_REQUIRED`, chờ bộ ground truth (GT) ẩn từ giảng viên để chấm điểm F1 chính thức.

## 00. Thông tin chung

| Mục | Giá trị |
|---|---|
| Mã nhóm | G11 (Làm bài cá nhân) |
| Challenge | T05 — Leakage & Near-Duplicate Guardian |
| Thành viên | Cao Quang Linh (MSSV: 2A202603050) — owner, tích hợp, thuật toán, reviewer và tác giả báo cáo |
| Git author/email | Rin111124 / caolinhcao12345@gmail.com (cấu hình Git cục bộ) |
| Git URL | https://github.com/Rin111124/K5-L2-Day06-CaoQuangLinh-2A202603050-DataGovernanceAndPrivacy |
| Tag demo/final | final-submission |
| Hạn nộp | Theo lịch công bố của giảng viên |

## 01. Bài toán

Ảnh gần trùng có thể xuất hiện đồng thời trong tập train và test. Khi đó mô
hình có thể trông như tổng quát hóa tốt, dù đã thấy nội dung gần giống ảnh test
trong lúc huấn luyện. Điều này làm sai lệch kết quả đánh giá và có thể khiến
người dùng sau này tin vào hiệu năng cao hơn thực tế.

PoC nhận `images.csv` và các ảnh, sau đó xuất các cặp nghi trùng, manifest chia
train/test theo nhóm, hàng đợi review và quyết định HOLD. Ghép nhầm có thể làm
mất dữ liệu hữu ích hoặc gom các cảnh không liên quan; bỏ sót cặp trùng có thể
để leakage giữa các split. Vì vậy kết quả vẫn HOLD cho đến khi review các cặp
rủi ro và đánh giá trên GT của giảng viên.

## 02. Dữ liệu và provenance

| Split | Quy mô | Nguồn / license | Mục đích |
|---|---:|---|---|
| Fixture T05 | 120 ảnh; tài liệu `docs/tracks/T05.md` mô tả 20 scene | Dữ liệu synthetic; CC0 theo README | Phát triển và demo tái lập |
| GT đánh giá của giảng viên | Không có trong checkout này | Overlay riêng của giảng viên | Chỉ dùng cho đánh giá chính thức; cần xin giảng viên |

Fixture có các cột `image_id`, đường dẫn ảnh tương đối `path`, `camera_id` và
`captured_at`; không có `scene_id` công khai. Pipeline không đọc thư mục `gt/`.
Preflight xác nhận hash trong manifest khớp. Seed là 42; các connected
component được chia xấp xỉ 70% train / 30% test. Bài không dùng dữ liệu người
hoặc biển số thật.

## 03. Thiết kế

Luồng xử lý: xác minh manifest → đọc ảnh → so SHA-256, pHash, dHash và tương
quan ảnh xám đã chuẩn hóa → xếp hạng cặp ứng viên → người review → gom các cặp
dự đoán trùng và burst cùng camera → chia train/test → ghi prediction, split,
decision và audit.

Ngưỡng hiện được cài trong `configs/tracks/t05.yaml`: nhận là trùng nếu SHA-256
giống hệt, hoặc tương quan >= 0.92, hoặc tương quan >= 0.78 đồng thời pHash
Hamming <= 8 và dHash Hamming <= 12. Quy tắc rộng hơn (tương quan >= 0.70 và
pHash Hamming <= 16) đưa cặp biên vào hàng đợi để người review. Contact sheet
ưu tiên các cặp gần ngưỡng tương quan; các cặp cùng SHA-256 được ưu tiên thấp
hơn vì nội dung byte giống hệt đã rõ ràng.

Các ngưỡng đánh giá đã được owner Cao Quang Linh xác nhận và đóng băng chính thức trong `reports/metric_contract.md` vào ngày 15/11/2026 trước khi tiếp cận dữ liệu ground truth ẩn của giảng viên.

Baseline so SHA-256 chính xác và chia ngẫu nhiên ở cấp ảnh. PoC bổ sung hash
cảm nhận cùng tương quan ảnh, sau đó dùng connected components để giữ các cặp
dự đoán trùng và burst cùng camera trong một split. Cách này chạy CPU/offline
phù hợp fixture 120 ảnh. So sánh mọi cặp có độ phức tạp O(N²); với dữ liệu lớn
hơn cần blocking hoặc chỉ mục tìm láng giềng gần đúng.

Tài liệu tham khảo (truy cập ngày 14-11-2026):

1. Christoph Zauner, *Implementation and Benchmarking of Perceptual Image Hash
   Functions* (2010), https://www.phash.org/docs/pubs/thesis_zauner.pdf — nền
   tảng về hash cảm nhận và các đánh đổi khi triển khai.
2. Ramos và cộng sự, *Data Leakage in Visual Datasets* (ICCV Workshops 2025),
   https://openaccess.thecvf.com/content/ICCV2025W/Findings/papers/Ramos_Data_Leakage_in_Visual_Datasets_ICCVW_2025_paper.pdf —
   lý do cần kiểm tra nội dung trùng giữa các split dữ liệu ảnh.
3. Đề bài trong repo: `docs/tracks/T05.md` — quy định output, metric, review
   và các failure mode của T05.

## 04. Baseline và kết quả chạy cục bộ

Cả hai lệnh dùng cùng fixture 120 ảnh, seed 42, offline và review budget B=20.
Các số sau là output của pipeline, không phải metric tính bằng GT.

| Quan sát | Baseline | PoC |
|---|---:|---:|
| Thời gian chạy một lần | 0.1624 giây | 0.6409 giây |
| Số dòng trong `suspect_pairs.csv` | 20 | 188 |
| Số cặp dự đoán dương tính | 20 cặp SHA-256 giống hệt | 133 |
| Ứng viên biên (`pred_dup=0`) | 0 | 55 |
| Kích thước hàng đợi review | 20 | 20 |
| Số ảnh theo split | 84 train / 36 test | 89 train / 31 test |
| Cặp dương tính dự đoán nằm ở hai split khác nhau | 7 cặp exact | 0 |

Số cặp cắt ngang split được tính từ prediction của từng phương pháp; đây không
phải metric residual leakage dựa trên GT. PoC có số 0 vì các cạnh dương tính do
chính nó dự đoán được dùng để tạo group split. Con số đó không phát hiện được
cặp trùng mà detector bỏ sót. Thời gian là một lần chạy trên fixture nhỏ,
không phải benchmark ổn định.

## 05. Quy trình đánh giá

Metric chính là **Leakage Detection F1 (pair)**; càng cao càng tốt. Đơn vị là
cặp không thứ tự của `image_id`. Một cặp đúng khi hai ảnh cùng `dup_group_id`
trong GT của giảng viên. Precision = TP/(TP+FP), recall = TP/(TP+FN), F1 là
trung bình điều hòa của precision và recall. Metric phụ gồm pair precision/
recall, false merge rate và residual cross-split leakage.

Ngưỡng, candidate pool, seed và budget được ghi trong
`reports/metric_contract.md`; không điều chỉnh sau khi xem GT. Đánh giá chính
thức hiện **đang chờ**, vì `fixtures/t05_near_duplicate/gt/gt_groups.csv` không
có trong repo. Báo cáo không tuyên bố F1, precision, recall hay GT leakage khi
chưa có dữ liệu. Khi nhận overlay, chạy evaluator cho baseline/PoC rồi dùng
`src.compare` tạo `reports/table1_baseline_vs_poc.md`.

## 06. Phân tích failure mode

1. **Baseline exact-hash bỏ sót near-duplicate đã biến đổi (False Negatives & Data Leakage):**
   Baseline chỉ so khớp mã băm SHA-256 tuyệt đối, do đó chỉ bắt được đúng 20 cặp trùng byte nguyên bản (ví dụ `im_000::im_001`). Khi ảnh bị biến đổi thời gian/burst (`im_000` và `im_004` chênh nhau 0.2s) hoặc biến đổi ánh sáng (`im_000` và `im_003`), mã hash SHA-256 thay đổi hoàn toàn khiến baseline bỏ sót toàn bộ. Khi chia tách tập train/test ngẫu nhiên độc lập theo từng ảnh, có tới 7 cặp trùng lặp tuyệt đối bị phân tán giữa train (84 ảnh) và test (36 ảnh), gây ra hiện tượng rò rỉ dữ liệu (data leakage) nghiêm trọng trong baseline.

2. **Bẫy False Merge giữa các scene khác nhau do tương đồng về màu sắc/histogram (Cross-scene Trap):**
   Trong fixture có các cặp ảnh thuộc các scene hoàn toàn khác nhau nhưng có màu sắc tổng thể và ánh sáng tương tự (ví dụ: các ảnh thuộc Scene 1 `im_006`..`im_011` trên cam_1 so với Scene 19 `im_114`..`im_119` trên cam_3). Độ tương quan ảnh xám chuẩn hóa giữa `im_006` và `im_114` đạt tới 0.8002. Nếu thuật toán chỉ dựa vào độ tương quan cường độ pixel hoặc histogram màu, hệ thống sẽ gộp nhầm Scene 1 và Scene 19 thành một cụm lớn (False Merge). Nhờ áp dụng đồng thời perceptual hash (`pHash` và `dHash`), vì khoảng cách Hamming pHash = 14 > 8 (`phash_max`), PoC đã đánh giá đúng cặp này là không trùng (`pred_dup=0`), loại bỏ thành công bẫy ghép nhầm giữa các scene khác nhau.

3. **Rò rỉ tiềm ẩn (Residual Leakage) do biến đổi mạnh đối với các ảnh biên chưa được gom cụm:**
   Trong các scene, ảnh thứ 3 (như `im_002`, `im_014`, `im_020`, `im_032`, `im_050`...) chịu các biến đổi mạnh hơn hoặc được chụp cách xa thời điểm burst (sau vài ngày). Ví dụ `im_014` so với `im_012` có tương quan chỉ 0.658, pHash distance = 10, dHash distance = 4. Do nằm ngoài ngưỡng tự động (`corr_min >= 0.92` hoặc `corr >= 0.78 & pHash <= 8`), các ảnh này chỉ được gán nhãn ứng viên biên (`pred_dup=0`) và không tự tạo cạnh trong đồ thị gom cụm. Khi phân chia train/test theo cụm thành phần liên thông, các node cô lập này (như `im_014`, `im_020`) bị thuật toán chia ngẫu nhiên sang tập `test` trong khi phần còn lại của scene nằm ở `train`, dẫn đến nguy cơ rò rỉ ngầm. Đây là lý do quy trình Human-in-the-loop đóng vai trò quyết định: con người can thiệp xem xét contact sheet để duyệt hoặc hiệu chỉnh các cặp biên này.

## 07. Human review và quyết định

Hàng đợi review ưu tiên `out/poc/review_queue.csv` gồm top B=20 cặp biên có độ ưu tiên cao nhất, kết hợp cùng giao diện trực quan offline `out/poc/contact_sheet.html`. Sinh viên đã hoàn thành quy trình review thực tế:
- Toàn bộ 20 cặp biên đã được thẩm định trực tiếp bởi reviewer **Cao Quang Linh**, ghi nhận quyết định `approve` và lý do đối chiếu chi tiết trong `out/poc/review_queue_reviewed.csv` (đã đồng bộ sang `reports/review_queue.csv`).
- Khi tái chạy PoC với file review, pipeline đã tự động đọc kết quả, cập nhật trạng thái nhãn và ghi nhận đầy đủ 20 hành vi kiểm toán vào `out/poc/audit_log.jsonl` (lưu trữ bất biến JSONL với timestamp UTC, actor, action, before, after và note).
- Quyết định quản trị dữ liệu cuối cùng được xuất ra `out/poc/decision.json` và `reports/decision_log.csv` với trạng thái **HOLD**, mã lý do `T05_REVIEW_AND_GT_REQUIRED`, người chịu trách nhiệm: `Cao Quang Linh-Reviewer`. Trạng thái HOLD tuân thủ nghiêm ngặt nguyên tắc quản trị và bảo vệ quyền riêng tư: dữ liệu chỉ được xem xét chuyển sang GO khi có kết quả đánh giá đối sánh độc lập từ tập ground truth ẩn của giảng viên.

## 08. Tái lập và kiểm thử

Môi trường thực thi: Windows, Python 3.11.9, pandas 2.2.3, seed 42.
- `tools.preflight`: Đạt 0 FAIL, 2 WARN (về thư mục data thật/model tùy chọn).
- `pytest`: Đạt **51 passed, 39 skipped** (0 failed). Bốn test đặc tả riêng cho T05 trong `tests/test_t05_pipeline.py` đều vượt qua:
  1. `test_pair_labels_separate_positive_from_borderline_candidate`: kiểm tra logic tách biệt cặp positive, candidate biên và negative.
  2. `test_components_keep_linked_images_together_and_singletons_separate`: kiểm tra thuật toán Disjoint Set Union (Union-Find) gom cụm chính xác.
  3. `test_t05_poc_runs_end_to_end_with_contract_and_split`: kiểm tra toàn bộ pipeline PoC E2E, bảo đảm output contract và không có cặp positive nào bị cắt ngang giữa train/test.
  4. `test_t05_baseline_runs_end_to_end_with_evidence`: kiểm tra pipeline baseline E2E và tính hợp lệ của bằng chứng evidence.

Các lệnh chuẩn để tái lập toàn bộ kết quả:
```powershell
# 1. Kiểm tra môi trường và tính toàn vẹn dữ liệu
python -m tools.preflight

# 2. Chạy Baseline và PoC
python -m src.main --config configs/lab.yaml --track t05 --output out/baseline --run-name baseline --pipeline src.examples.t05_baseline --offline --seed 42
python -m src.main --config configs/lab.yaml --track t05 --output out/poc --run-name poc --offline --seed 42

# 3. Chạy toàn bộ test suite
pytest -q
```

## 09. Giới hạn, đóng góp và việc hoàn tất nộp bài

- **Giới hạn kỹ thuật:** Thuật toán sử dụng kết hợp tương quan ảnh xám chuẩn hóa và perceptual hash (pHash/dHash) với độ phức tạp so sánh theo cặp $O(N^2)$. Với tập dữ liệu quy mô hàng triệu ảnh, cần tích hợp thêm kỹ thuật LSH (Locality-Sensitive Hashing) hoặc FAISS/vector indexing để lọc ứng viên trước khi so khớp chi tiết. Dữ liệu fixture là synthetic 120 ảnh mô phỏng; khi triển khai trên dữ liệu thực tế (như camera giám sát, BDD100K) cần có quy trình rà soát PII (biển số, khuôn mặt) và giấy phép bản quyền rõ ràng.
- **Phân công và đóng góp:** Sinh viên Cao Quang Linh thực hiện bài tập độc lập (solo), đảm nhiệm toàn bộ các khâu: phân tích bài toán, xây dựng thuật toán PoC và Baseline, thiết kế test suite, thực hiện human review, phân tích failure mode và hoàn thiện báo cáo. Thông tin đóng góp được ghi nhận tại `reports/team_contributions.csv`.
- **Cam kết liêm chính:** Quá trình thực hiện tuân thủ quy định học tập, sử dụng công cụ AI hỗ trợ theo đúng nguyên tắc minh bạch, trung thực và tự kiểm chứng toàn bộ code cũng như kết quả thực nghiệm.
