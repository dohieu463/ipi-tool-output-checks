# Thực nghiệm: kiểm tra đầu ra công cụ chống indirect prompt injection

[![checks](https://github.com/dohieu463/ipi-tool-output-checks/actions/workflows/ci.yml/badge.svg)](https://github.com/dohieu463/ipi-tool-output-checks/actions/workflows/ci.yml)

Code cho bài báo *Checking Tool Outputs Against Indirect Prompt Injection: An Empirical
Study of the Security–Utility–Cost Trade-off in LLM Agents*.

**Trạng thái: đã hoàn tất.** Toàn bộ số liệu nằm trong `results/`, bảng và hình trong
`paper_outputs/`, `paper_outputs_seeds/`, `paper_outputs_ablation/`.
Tài liệu bàn giao cho phần viết bài: [`METHODS_AND_RESULTS.md`](METHODS_AND_RESULTS.md).
Lịch sử sửa code: [`CHANGELOG_CODE.md`](CHANGELOG_CODE.md).

## Kết quả chính (3 seed, gpt-4o-mini-2024-07-18)

`important_instructions`, 249 cặp (slack 105 + banking 144), mean ± sd qua 3 lần chạy:

| Defense | BU % | UA % | ASR % | p vs none | FPR benign % |
|---|---|---|---|---|---|
| No defense | 71.2 ± 3.1 | 50.3 ± 3.5 | 54.8 ± 1.2 | – | – |
| Spotlighting (delimiters) | 64.0 ± 4.1 | 49.9 ± 1.7 | 52.2 ± 1.2 | 0.31 / 0.14 / 1 | – |
| Repeat user prompt | 64.0 ± 1.6 | 44.0 ± 0.6 | 21.8 ± 1.9 | có ý nghĩa | – |
| Regex detector | 66.7 ± 1.6 | 24.2 ± 3.8 | 0.0 | có ý nghĩa | 0.0 |
| DeBERTa (block output) | 36.0 ± 3.1 | 30.4 ± 2.5 | 10.6 ± 0.2 | có ý nghĩa | 86.1 ± 2.3 |
| LLM detector | 62.2 ± 0.0 | 24.0 ± 5.2 | 0.0 | có ý nghĩa | 3.6 ± 0.2 |
| **LLM sanitizer** | 58.6 ± 1.6 | **49.5 ± 0.6** | **0.0** | có ý nghĩa | 14.9 ± 1.8 |

Ba kết luận: (1) prompt-level defense không có tác dụng; (2) chỉ sanitizer đạt ASR 0 mà
không mất utility; (3) policy "chặn toàn bộ output" mới là thứ phá utility, không phải
bản thân classifier (xem ablation bên dưới).

## Môi trường đã dùng

| Thành phần | Phiên bản |
|---|---|
| Python | 3.12.13 (via `uv`) |
| agentdojo | 0.1.35, benchmark `v1.2.2` |
| torch | 2.15.0+cpu (không GPU) |
| transformers | 5.22.1 |
| openai | 3.42.0 |
| Model | `gpt-4o-mini-2024-07-18` (agent + checker) |

`transformers` 5.x chạy được với DeBERTa của AgentDojo (đã kiểm chứng: load 24s, phân loại
đúng). Không cần GPU.

## Cài đặt

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
# CPU wheel trước, nếu không pip sẽ kéo bản CUDA ~2.5 GB
uv pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.2.1"
uv pip install -r requirements.txt
cp .env.example .env        # điền OPENAI_API_KEY
python scripts/preflight.py # kiểm tra gateway, tool-call, detector, sanitizer
```

`.env`:

```bash
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=                        # rỗng = api.openai.com
OPENAI_MODEL=gpt-4o-mini-2024-07-18
CHECKER_MODEL=                          # rỗng = dùng cùng model agent
OPENAI_TIMEOUT=120
OPENAI_MAX_RETRIES=8
```

## Cấu hình được so sánh

| Tên | Nguồn | Cơ chế |
|---|---|---|
| `none` | – | baseline |
| `spotlighting_with_delimiting` | AgentDojo | bọc output trong `<< >>` + dặn model |
| `repeat_user_prompt` | AgentDojo | nhắc lại yêu cầu sau mỗi tool output |
| `regex_detector` | tự viết | 8 regex; khớp thì **thay toàn bộ** output |
| `transformers_pi_detector` | AgentDojo | DeBERTa (ProtectAI); flag thì **thay toàn bộ** output |
| `transformers_line_filter` | tự viết (**ablation**) | cùng DeBERTa, nhưng chỉ **xoá từng dòng** bị flag |
| `llm_detector` | tự viết | LLM trả `INJECTION`/`CLEAN`; flag thì thay toàn bộ output |
| `llm_sanitizer` | tự viết | LLM viết lại output, xoá đoạn độc hại, giữ dữ liệu |

Hai attack: `important_instructions` (chuẩn AgentDojo, kết quả chính) và `casual_note`
(tự viết, giấu mục tiêu trong dòng P.S., dùng để kiểm tra tổng quát hoá).

## Chạy

Script chính là `scripts/run_batch.sh`; mọi tham số qua biến môi trường để nhiều batch
chạy song song mà không ghi đè log/kết quả của nhau.

```bash
# Một seed đầy đủ (12 cấu hình)
RESULTS_DIR=results/seed-1 LOGDIR=runs/seed-1 TAG=seed1 SEED=1 \
  ATTACKS="important_instructions casual_note" MAX_PARALLEL=4 \
  bash scripts/run_batch.sh

# Chỉ ablation
TAG=ablation RESULTS_DIR=results/ablation LOGDIR=runs/ablation \
  MAIN_DEFENSES="transformers_line_filter" GEN_DEFENSES="transformers_line_filter" \
  bash scripts/run_batch.sh

# Checker mạnh hơn
TAG=checker RESULTS_DIR=results/checker-gpt4o LOGDIR=runs/checker-gpt4o \
  CHECKER_MODEL=gpt-4o MAIN_DEFENSES="llm_detector llm_sanitizer" \
  ATTACKS="important_instructions" MAX_PARALLEL=1 bash scripts/run_batch.sh
```

Mỗi job được retry tối đa 4 lần (mặc định) và bỏ qua suite đã xong, nên chạy lại lệnh cũ
sẽ tiếp tục chứ không làm lại từ đầu. `MAX_PARALLEL=4` là mức an toàn cho tier 1 của
OpenAI và cho RAM 14 GB (tối đa 2 process DeBERTa cùng lúc).

## Phân tích

```bash
python analyze.py --results results/seed-1 --out paper_outputs
python analyze_seeds.py results/seed-1 results/seed-2 results/seed-3 --out paper_outputs_seeds
python analyze.py --results results/ablation --out paper_outputs_ablation
```

`analyze.py` sinh bảng + hình cho một lần chạy (Wilson CI, McNemar exact).
`analyze_seeds.py` gộp nhiều seed thành mean ± sd và báo p-value **theo từng seed**
(không gộp các seed thành một p-value, vì chúng là các lần chạy độc lập).

## Ý nghĩa chỉ số

- **BU**: % task hoàn thành khi không bị tấn công.
- **UA**: % task hoàn thành khi có injection.
- **ASR**: % cặp mà agent thực hiện mục tiêu kẻ tấn công.
- **Benign flag rate**: % tool output bị gắn cờ khi không có tấn công (dương tính giả).
- **USD / task**: đo ở pha không tấn công. Với OpenAI, đây là **ước tính** từ token theo
  bảng giá trong `ipi_eval/usage.py` (API không trả giá); với gateway OpenCode thì lấy
  `usage.opencode.allowance` do gateway trả về.
- **p**: McNemar exact trên cùng cặp `(suite, user_task, injection_task)`.

## Chi phí và thời gian đã dùng

| Batch | USD | Ghi chú |
|---|---|---|
| Pilot (không seed) | 6.16 | dùng để phát hiện vấn đề, không dùng trong bài |
| seed-1 | 7.04 | 12 cấu hình |
| seed-2 | 4.43 | 7 cấu hình `important_instructions` |
| seed-3 | 4.63 | 7 cấu hình `important_instructions` |
| Ablation | 2.13 | DeBERTa line filter |
| Checker gpt-4o | 3.95 | tính lại từ token (JSON ghi $0.60 do thiếu bảng giá lúc chạy) |
| **Tổng** | **≈ $28.3** | ~10 giờ wall-clock với 3–4 process song song |

## Cấu trúc

```
ipi_eval/defenses.py       8 defense + pipeline builder + checker retry
ipi_eval/attacks.py        casual_note + đăng ký tên model cho AgentDojo
ipi_eval/usage.py          token, latency, cost/allowance, seed injection
run_experiment.py          chạy 1 cấu hình
analyze.py                 bảng + hình cho 1 lần chạy
analyze_seeds.py           mean ± sd qua nhiều seed
scripts/run_batch.sh       runner bền (retry, resume, log riêng)
scripts/run_grid.sh        runner cũ cho toàn grid (giữ để tham khảo)
scripts/finalize.sh        rebuild toàn bộ artifact
scripts/preflight.py       kiểm tra gateway/model trước khi đốt tiền
```

## Lưu ý tái lập

1. `seed` của OpenAI là best-effort, không đảm bảo tái lập tuyệt đối. Báo cáo sd thực đo.
2. `casual_note` mới có 2 lần chạy (pilot + seed-1); seed-2/3 chỉ chạy
   `important_instructions`.
3. `regex_detector` trùng mẫu với template `important_instructions`; kết quả của nó là
   **optimistic bound**, và chính `casual_note` cho thấy nó không tổng quát hoá.
4. Chi phí là ước tính từ token, không phải số tiền OpenAI đã trừ.
5. Ablation dùng baseline của lần chạy pilot (cùng ngày), không phải mean 3 seed.

## License & citation

- **Code**: MIT — xem [`LICENSE`](LICENSE).
- **Kết quả và dữ liệu** (`results/`, `results_probe*/`, `paper_outputs*/`):
  CC BY 4.0 — xem [`LICENSE-DATA`](LICENSE-DATA).
- Trích dẫn: xem [`CITATION.cff`](CITATION.cff). Citation của bài báo sẽ được bổ sung khi
  bài được công bố.

Không có API key hay dữ liệu cá nhân trong repo này; `.env` bị `.gitignore` chặn.
`runs/` (log hội thoại đầy đủ, ~161 MB) được giữ ngoài repo và gửi riêng khi có yêu cầu.

