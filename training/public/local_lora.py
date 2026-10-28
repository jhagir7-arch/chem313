"""Pinned, local-only D005 Qwen pilot. No model execution is connected to OpenChem."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MODEL_ID = "Qwen/Qwen3.5-2B-Base"
REVISION = "b1485b2fa6dfa1287294f269f5fb618e03d52d7c"
SOURCE = ROOT / "training/upstream/D005/OpenChem_D005_Fourfold_Distillation_2026-10-17/generated/tool_operator"
EXPECTED = {
    "train": "cc7f5d22e43c8dc17698d5c6946ffd1da126b17c9b2d3c56d0c199ac5db60c2d",
    "valid": "914ab1130acedffdaeea3178a7151cd345ebf6bb28ffec340fb0647bc062ec08",
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def prepare(tokenizer, output, max_length):
    """Validate exact source bytes, masking and lengths; never truncate labels."""
    from mlx_lm.tuner.datasets import CacheDataset, ChatDataset

    class NoThinking:
        def apply_chat_template(self, *args, **kwargs):
            return tokenizer.apply_chat_template(*args, **kwargs, enable_thinking=False)

    datasets, audit, prompt_sets = {}, {}, {}
    for split, expected in EXPECTED.items():
        source = SOURCE / f"{split}.jsonl"
        if sha(source) != expected:
            raise ValueError(f"Source hash mismatch: {split}")
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        converted, lengths, prompt_hashes = [], [], set()
        for row in rows:
            messages = row["prompt"] + row["completion"]
            if len(row["completion"]) != 1 or messages[-1]["role"] != "assistant":
                raise ValueError("Expected one assistant completion")
            json.loads(messages[-1]["content"])
            tokens = NoThinking().apply_chat_template(messages, return_dict=False)
            prefix = NoThinking().apply_chat_template(messages[:-1], add_generation_prompt=True, return_dict=False)
            if tokens[:len(prefix)] != prefix or len(tokens) <= len(prefix):
                raise ValueError("Completion masking does not align")
            if len(tokens) > max_length:
                raise ValueError(f"Refusing truncation: {len(tokens)} tokens")
            prompt_hashes.add(hashlib.sha256(json.dumps(row["prompt"], sort_keys=True).encode()).hexdigest())
            converted.append({"messages": messages})
            lengths.append(len(tokens))
        prompt_sets[split] = prompt_hashes
        (output / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in converted))
        datasets[split] = CacheDataset(ChatDataset(converted, NoThinking(), mask_prompt=True))
        audit[split] = {"rows": len(rows), "source_sha256": expected, "max_tokens": max(lengths),
                        "min_tokens": min(lengths), "converted_sha256": sha(output / f"{split}.jsonl")}
    overlap = prompt_sets["train"] & prompt_sets["valid"]
    audit["identical_prompt_overlap"] = len(overlap)
    if overlap:
        raise ValueError(f"Exact train/validation prompt overlap: {len(overlap)}")
    audit["limits"] = "Synthetic developer-visible validation; related templates may cross splits. Not a blind scientific benchmark. Older RC2 actions do not cover orca.prepare_input."
    write_json(output / "data_audit.json", audit)
    return datasets, audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--iters", type=int, default=100)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.iters < 1:
        parser.error("iters must be positive")
    run = args.run.resolve()
    run.mkdir(parents=True, exist_ok=True)
    if (run / "status.json").exists():
        parser.error("Use a fresh run directory; existing evidence is immutable")
    os.environ["TRACKIO_DIR"] = str(run / "trackio")
    for key in ("TRACKIO_SPACE_ID", "TRACKIO_SERVER_URL", "TRACKIO_DATASET_ID", "TRACKIO_BUCKET_ID", "TRACKIO_REGISTRY_BUCKET_ID"):
        os.environ.pop(key, None)
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from transformers import AutoTokenizer
    from huggingface_hub import snapshot_download
    import mlx.core as mx
    import mlx.optimizers as optim
    import numpy as np
    from mlx.utils import tree_flatten
    from mlx_lm.utils import load
    from mlx_lm.tuner.trainer import train, TrainingArgs
    from mlx_lm.tuner.callbacks import TrainingCallback
    from mlx_lm.tuner.utils import linear_to_lora_layers

    model_path = ROOT / "training/models/Qwen3.5-2B-Base"
    snapshot_download(MODEL_ID, revision=REVISION, local_dir=model_path,
                      allow_patterns=["*.safetensors", "model.safetensors.index.json", "config.json", "tokenizer*", "vocab.json", "merges.txt", "LICENSE", "README.md"])
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    datasets, audit = prepare(tokenizer, run, 1024)
    config = {"model": MODEL_ID, "revision": REVISION, "model_path": str(model_path), "data": "D005/tool_operator",
              "seed": 175117, "fine_tune_type": "lora", "num_layers": 8,
              "lora_parameters": {"rank": 8, "scale": 16.0, "dropout": 0.0},
              "learning_rate": 0.0001, "batch_size": 1, "gradient_accumulation": 4,
              "iters": args.iters, "max_seq_length": 1024, "mask_prompt": True,
              "enable_thinking": False, "grad_checkpoint": True, "resume": str(args.resume) if args.resume else None,
              "validation_batches": 8, "external_reporting": False,
              "model_files": {p.name: sha(p) for p in model_path.iterdir() if p.is_file()}}
    if config["model_files"].get("model.safetensors-00001-of-00001.safetensors") != "928acbf11878c32185bbd863514d191769285065ab9ea14fbfe431303f5fdf2d":
        raise ValueError("Pinned model weight checksum mismatch")
    write_json(run / "run_config.json", config)
    if args.prepare_only:
        print(json.dumps(audit), flush=True)
        return
    mx.random.seed(config["seed"])
    np.random.seed(config["seed"])
    # Leave headroom for the desktop and scientific workers.
    mx.set_memory_limit(14 * 1024**3)
    mx.set_cache_limit(512 * 1024**2)
    status = {"state": "loading", "pid": os.getpid(), "started_utc": datetime.now(timezone.utc).isoformat(), "iteration": 0}
    write_json(run / "status.json", status)
    model, _ = load(str(model_path), trust_remote_code=False)
    model.freeze()
    linear_to_lora_layers(model, config["num_layers"], config["lora_parameters"])
    if args.resume:
        model.load_weights(str(args.resume), strict=False)
    adapter_dir = run / "adapter"
    adapter_dir.mkdir()
    write_json(adapter_dir / "adapter_config.json", config)
    initial = adapter_dir / "initial.safetensors"
    mx.save_safetensors(str(initial), dict(tree_flatten(model.trainable_parameters())))
    initial_sha = sha(initial)
    config["trainable_parameters"] = sum(v.size for _, v in tree_flatten(model.trainable_parameters()))
    write_json(run / "run_config.json", config)
    import trackio
    trackio.init(project="OpenChem-local", name=run.name, config=config, space_id=None,
                 auto_log_gpu=False, auto_log_cpu=False, embed=False)

    class Evidence(TrainingCallback):
        def report(self, kind, info):
            if not all(math.isfinite(v) for v in info.values() if isinstance(v, (int, float))):
                raise FloatingPointError("Nonfinite training metric")
            event = {"kind": kind, **info, "utc": datetime.now(timezone.utc).isoformat()}
            with (run / "metrics.jsonl").open("a") as f:
                f.write(json.dumps(event, allow_nan=False) + "\n")
                f.flush()
            status.update(state="training", **event)
            write_json(run / "status.json", status)
            trackio.log({f"{kind}/{k}": v for k, v in info.items() if k != "iteration"}, step=info["iteration"])
            print(json.dumps(event), flush=True)

        def on_train_loss_report(self, info):
            self.report("train", info)

        def on_val_loss_report(self, info):
            self.report("validation", info)

    try:
        train(model, optim.Adam(config["learning_rate"]), datasets["train"], datasets["valid"],
              args=TrainingArgs(batch_size=1, iters=args.iters, val_batches=8, steps_per_report=4,
                                steps_per_eval=50, steps_per_save=20, max_seq_length=1024,
                                adapter_file=adapter_dir / "adapters.safetensors", grad_checkpoint=True,
                                grad_accumulation_steps=4, clear_cache_threshold=512 * 1024**2),
              training_callback=Evidence())
        final = adapter_dir / "adapters.safetensors"
        trained = mx.load(str(final))
        original = mx.load(str(initial))
        changed = sum(bool(mx.any(trained[k] != original[k]).item()) for k in trained)
        if not changed:
            raise RuntimeError("No adapter tensors changed")
        model.load_weights(str(final), strict=False)
        status.update(state="complete", iteration=args.iters, optimizer_updates=args.iters // 4,
                      adapter_sha256=sha(final), initial_sha256=initial_sha, changed_tensors=changed,
                      peak_memory_bytes=mx.get_peak_memory(), completed_utc=datetime.now(timezone.utc).isoformat())
        write_json(run / "status.json", status)
    except BaseException as exc:
        status.update(state="failed", error=f"{type(exc).__name__}: {exc}")
        write_json(run / "status.json", status)
        raise
    finally:
        trackio.finish()


if __name__ == "__main__":
    main()
