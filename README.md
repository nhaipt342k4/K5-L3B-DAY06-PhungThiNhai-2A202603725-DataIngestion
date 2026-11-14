# Bài làm Day 06: Phùng Thị Nhài (2A202603725, L3B)

Corpus: Datio English, *Xây nền ngữ pháp trong 30 ngày* (40 trang nội dung). Embedding: `intfloat/multilingual-e5-small` (chạy local). Vector store: Chroma (cosine). Báo cáo: [report/individual/2A202603725_PhungThiNhai.md](report/individual/2A202603725_PhungThiNhai.md).

## Cài đặt (Windows PowerShell; macOS/Linux dùng lệnh tương đương)

Yêu cầu: Python 3.12 (đã thử 3.12.10). Không cần Docker, không cần API key.

```powershell
cd starter
python -m venv .venv
.venv\Scripts\Activate.ps1          # nếu bị chặn: Set-ExecutionPolicy -Scope Process Bypass
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
$env:PYTHONUTF8 = "1"
```

**Dữ liệu:** PDF không được commit vì tài liệu không ghi giấy phép tái phân phối. Tải `Datio_English_Grammar_Foundation_30_Days.pdf` từ thư viện tự học tại ieltsdatio.edu.vn và đặt vào `starter/data/`. Chi tiết nguồn, quy tắc đếm trang và 7 trang bị loại xem [data/manifest.json](data/manifest.json). Lần chạy đầu sẽ tự tải model (~470 MB).

## Chạy lại toàn bộ (từ `starter/`)

```powershell
python -m scripts.prepare_data                         # manifest + kiểm tra evidence (25 câu)
python -m src.run index                                # chunk A/B/D, embed, lưu Chroma, kiểm tra nạp lại
python -m src.run evaluate --split dev                 # A, B, C, D trên 15 câu dev
python -m src.run select                               # áp tiêu chí đã chốt cho A/B/C
python -m src.run evaluate --split test                # test gốc (5 câu)
python -m src.run evaluate --split test2               # test mới cho phần cải tiến D
python -m src.run evaluate --split test --strategies D # D trên test gốc, lưu riêng nhãn __posthoc
python -m src.run audit                                # không ghi đè file CSV đã có nhãn
```

Lưu ý: `evaluate --split dev` khi không có `--strategies` sẽ chạy cả D. Kết quả D ở lần chạy gốc nằm dưới tag `dev__D`.

## Bản đồ file

| Nội dung | Đường dẫn |
|---|---|
| Code pipeline | [starter/src/](starter/src/) (`ingestion`, `chunking`, `embeddings`, `store`, `evaluation`, `run`) |
| Manifest dữ liệu | [data/manifest.json](data/manifest.json) |
| Benchmark (15 dev / 5 test) và test2 (5 câu) | [benchmark/](benchmark/) |
| Tiêu chí chọn và kết quả chọn | [starter/results/selection.json](starter/results/selection.json) |
| Thống kê index | [starter/results/index_stats.json](starter/results/index_stats.json) |
| Chỉ số Hit@1 / Hit@3 | [starter/results/metrics.json](starter/results/metrics.json) |
| Trace top-3 đầy đủ | `starter/results/traces_*.jsonl` |
| Nhãn chấm tay và tổng hợp | `starter/results/audit_*.csv`, [audit_summary.json](starter/results/audit_summary.json) |
| Kiểm tra evidence | [starter/results/evidence_verification.json](starter/results/evidence_verification.json) |
| Experiment log | [artifacts/experiment_log.csv](artifacts/experiment_log.csv) |
| Tiến độ và quyết định | [PROGRESS.md](PROGRESS.md) |

---

# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.
