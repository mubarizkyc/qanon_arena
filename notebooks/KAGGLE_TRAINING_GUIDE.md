# Kaggle QLoRA Fine-Tuning Guide (Group G03 — M2 + A1)

This guide explains how to run [`notebooks/finetune_qlora.ipynb`](finetune_qlora.ipynb) on **Kaggle** to produce the `A1` QLoRA SFT adapter for **Group G03** (`M2` Fact Memory + `A1` SFT), and how to evaluate all four required configurations locally or in a GPU environment.

---

## 1. Prerequisites

- A Kaggle account (phone-verified so GPU and Internet toggles are enabled).
- Your `qanon_arena` repository pushed to GitHub (`https://github.com/mubarizkyc/qanon_arena.git`), or archived as a Kaggle Dataset if running from an attached input.
- No changes to `harness/`, `harness/config.yaml`, or the official datasets.

---

## 2. Import the Notebook into Kaggle

1. Go to [Kaggle](https://www.kaggle.com/) → **Create** → **New Notebook**.
2. In the top menu, select **File** → **Import Notebook**.
3. Upload `notebooks/finetune_qlora.ipynb` (or import it directly from your GitHub repository).

---

## 3. Configure Kaggle Notebook Settings

In the right-hand **Notebook** sidebar (or **Settings**):

1. **Accelerator:** Select **GPU T4** (preferred) or **GPU T4 x2**.
   - Note: `T4 x2` provides two separate 16 GB GPUs, not one 32 GB GPU. The notebook automatically detects multiple GPUs and pins `CUDA_VISIBLE_DEVICES=0` so QLoRA runs cleanly on a single 16 GB T4 without `DataParallel` errors.
2. **Internet:** Toggle **Internet ON** (required to install packages and download `Qwen/Qwen3-4B-Instruct-2507` from Hugging Face Hub, and to clone the GitHub repo).
3. **Persistence (Optional):** Set **Persistence** to *Files only* if you want `/kaggle/working/` preserved across session pauses.
4. **Hugging Face Token (Optional):** `Qwen/Qwen3-4B-Instruct-2507` is a public Apache-2.0 model. If you hit Hub rate limits or use a private mirror, open **Add-ons** → **Secrets**, create a secret named `HF_TOKEN`, and enable it for the notebook. Never hardcode tokens in cells.

---

## 4. Run the Training Pipeline

Run the notebook top-to-bottom (**Run All**, or execute sections **1** through **9** sequentially):

1. **Section 1 — Environment setup:** Installs `"transformers>=4.51.0,<5.0"`, `peft`, `trl`, `accelerate`, `bitsandbytes`, `datasets`, `langgraph`, and `pyyaml` without upgrading Kaggle's preinstalled PyTorch/CUDA.
2. **Section 2 — GPU verification:** Runs `nvidia-smi`, verifies CUDA availability (stops with an error if no GPU is active), and prints exact package and GPU details.
3. **Section 3 — Repository setup:** Clones/locates `/kaggle/working/qanon_arena/`, sets `GROUP = "G03"` and `TRAIN_TYPE = "A1"`, and configures `/kaggle/working/` output paths.
4. **Section 4 — Dataset & model verification:** Runs `python -m harness.build_sft_data` and `python -m harness.leakage_check`, verifies schema and non-emptiness, and verifies `Qwen/Qwen3-4B-Instruct-2507` access.
5. **Section 5 — QLoRA configuration:** Loads the base model in 4-bit NF4 (`float16`), configures LoRA (`r=16`, `alpha=32`, `dropout=0.05`), and confirms target modules exist.
6. **Section 6 — SFT training:** Runs `SFTTrainer` for `2` epochs (`lr=2e-4`, `max_seq_len=2048`, `seed=13`, `completion_only_loss=True`) and records training duration and peak VRAM.
7. **Section 7 — Metrics & timing:** Plots the training loss curve to `/kaggle/working/sft_loss.png` and prints a JSON summary for `MODEL_CARD.md` and `report/section.tex`.
8. **Section 8 — Adapter saving & validation:** Saves the unmerged PEFT adapter and tokenizer to `/kaggle/working/adapters/a1/` and reloads it onto a fresh 4-bit base model to verify integrity.
9. **Section 9 — Adapter ZIP creation:** Packages `a1/` into `/kaggle/working/a1_adapter.zip`.

---

## 5. Download Outputs from Kaggle

Once Section 9 completes:

1. Open the right-hand **Output** pane (`/kaggle/working/`).
2. Download:
   - `a1_adapter.zip`
   - `sft_loss.png`
3. Also copy the printed JSON summary from Section 7 so you have exact start/end times, duration, GPU model/VRAM, and training loss values for `MODEL_CARD.md` and `report/section.tex`.

---

## 6. Transfer the Adapter into Your Local Repository

Extract `a1_adapter.zip` into the `adapters/` directory at the root of your local `qanon_arena` repository. Because the ZIP contains a top-level `a1/` folder, extracting into `adapters/` produces:

```text
qanon_arena/
└── adapters/
    └── a1/
        ├── adapter_config.json
        ├── adapter_model.safetensors
        ├── tokenizer.json
        ├── tokenizer_config.json
        └── ...
```

On Windows PowerShell (from `qanon_arena/`):

```powershell
New-Item -ItemType Directory -Force -Path adapters | Out-Null
Expand-Archive -Path "$HOME\Downloads\a1_adapter.zip" -DestinationPath adapters -Force
Get-ChildItem adapters\a1
```

On Linux / macOS (from `qanon_arena/`):

```bash
mkdir -p adapters
unzip -o ~/Downloads/a1_adapter.zip -d adapters/
ls -la adapters/a1
```

---

## 7. Run the Four-Version Evaluation (G03 — M2 + A1)

Run all four configurations (`V1`–`V4`) across all three fixed seeds (`13`, `42`, `2026`) from the `qanon_arena/` root using the official `hf` backend:

```bash
# V1: M0 + A0 (baseline)
python -m harness.evaluate --group G03 --memory M0 --adapter A0 --split dev --all-seeds

# V2: M2 + A0 (fact memory only)
python -m harness.evaluate --group G03 --memory M2 --adapter A0 --split dev --all-seeds

# V3: M0 + A1 (SFT adapter only)
python -m harness.evaluate --group G03 --memory M0 --adapter A1 --adapter-path adapters/a1 --split dev --all-seeds

# V4: M2 + A1 (fact memory + SFT adapter)
python -m harness.evaluate --group G03 --memory M2 --adapter A1 --adapter-path adapters/a1 --split dev --all-seeds

# Generate the 2x2 summary table and confidence intervals
python -m harness.summarize --group G03 --split dev
```

Or run everything in one script (Bash / WSL / Git Bash / Kaggle):

```bash
bash scripts/run_all.sh G03 M2 A1 ./adapters/a1
```

> **Reminder:** Never modify `harness/`, never train on `dev.jsonl` / `smoke.jsonl` / `contrib/` / secret test questions, and record any unavoidable environment notes in `DEVIATIONS.md` if applicable.

