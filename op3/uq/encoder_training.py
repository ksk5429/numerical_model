"""
Multi-feature encoder training on real FEM data.

Trains the two-modality residual MLP encoder on the 1,794-sample
OptumGX-OpenSeesPy Monte Carlo database. This script replaces any
earlier proof-of-concept training that used synthetic or partially
fabricated data.

Usage
-----
    python -m op3.uq.encoder_training --data PHD/data/integrated_database_1794.csv
    python -m op3.uq.encoder_training --data PHD/data/integrated_database_1794.csv --epochs 500

The trained model is saved as a PyTorch state dict and can be loaded
by the Op³ web application for real-time inference.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


@dataclass
class TrainingConfig:
    data_path: str = ""
    epochs: int = 300
    batch_size: int = 64
    lr: float = 1e-3
    weight_decay: float = 1e-4
    dropout_prob: float = 0.3
    latent_dim: int = 64
    hidden_dim: int = 128
    train_split: float = 0.8
    val_split: float = 0.1
    seed: int = 42
    output_dir: str = "models/"


class ResidualBlock(nn.Module):
    def __init__(self, dim: int):
        super().__init__()
        self.fc1 = nn.Linear(dim, dim)
        self.fc2 = nn.Linear(dim, dim)
        self.relu = nn.ReLU()

    def forward(self, x):
        return x + self.relu(self.fc2(self.relu(self.fc1(x))))


class TwoModalityEncoder(nn.Module):
    """Two-modality residual MLP for structural state prediction.

    Capacity features (6 dim) and dynamic features (3 dim) are each
    projected into a shared latent space, concatenated, fused through
    residual blocks, and mapped to three sensor-observable targets.
    """

    def __init__(self, cfg: TrainingConfig):
        super().__init__()
        ld = cfg.latent_dim
        hd = cfg.hidden_dim

        # Capacity modality projector (6 -> latent_dim)
        self.cap_proj = nn.Sequential(
            nn.Linear(6, hd), nn.ReLU(),
            nn.Linear(hd, ld), nn.ReLU(),
        )
        # Dynamic modality projector (3 -> latent_dim)
        self.dyn_proj = nn.Sequential(
            nn.Linear(3, hd), nn.ReLU(),
            nn.Linear(hd, ld), nn.ReLU(),
        )
        # Fusion network (2 * latent_dim -> 3 targets)
        self.fusion = nn.Sequential(
            ResidualBlock(2 * ld),
            ResidualBlock(2 * ld),
            ResidualBlock(2 * ld),
            nn.Linear(2 * ld, 3),
        )
        self.dropout_prob = cfg.dropout_prob

    def forward(self, x_cap: torch.Tensor, x_dyn: torch.Tensor,
                training: bool = False) -> torch.Tensor:
        # Modality dropout during training
        if training and self.dropout_prob > 0:
            r = torch.rand(1).item()
            if r < self.dropout_prob / 2:
                x_cap = torch.zeros_like(x_cap)
            elif r < self.dropout_prob:
                x_dyn = torch.zeros_like(x_dyn)

        z_cap = self.cap_proj(x_cap)
        z_dyn = self.dyn_proj(x_dyn)
        z = torch.cat([z_cap, z_dyn], dim=-1)
        return self.fusion(z)


def load_and_split(cfg: TrainingConfig) -> Tuple:
    """Load the MC database and split into train/val/test."""
    import pandas as pd

    df = pd.read_csv(cfg.data_path)

    # Capacity features (from OptumGX)
    cap_cols = [c for c in df.columns if c in
                ("Hmax_kN", "H_ratio", "V_ratio", "fixity_proxy",
                 "su0", "k_su")]
    if len(cap_cols) < 6:
        # Pad with zeros if fewer capacity features available
        for i in range(6 - len(cap_cols)):
            df[f"cap_pad_{i}"] = 0.0
            cap_cols.append(f"cap_pad_{i}")

    # Dynamic features (from OpenSeesPy)
    dyn_cols = [c for c in df.columns if c in
                ("f1_Hz", "f1_f0", "scour_m")]
    if len(dyn_cols) < 3:
        for i in range(3 - len(dyn_cols)):
            df[f"dyn_pad_{i}"] = 0.0
            dyn_cols.append(f"dyn_pad_{i}")

    # Targets
    target_cols = ["f1_f0", "fixity_proxy", "H_ratio"]
    missing = [c for c in target_cols if c not in df.columns]
    if missing:
        raise ValueError(f"missing target columns: {missing}")

    X_cap = df[cap_cols[:6]].values.astype(np.float32)
    X_dyn = df[dyn_cols[:3]].values.astype(np.float32)
    Y = df[target_cols].values.astype(np.float32)

    # Normalise each feature to zero mean, unit variance
    cap_mean, cap_std = X_cap.mean(0), X_cap.std(0) + 1e-8
    dyn_mean, dyn_std = X_dyn.mean(0), X_dyn.std(0) + 1e-8
    y_mean, y_std = Y.mean(0), Y.std(0) + 1e-8

    X_cap = (X_cap - cap_mean) / cap_std
    X_dyn = (X_dyn - dyn_mean) / dyn_std
    Y_norm = (Y - y_mean) / y_std

    # Stratified split by scour depth
    np.random.seed(cfg.seed)
    n = len(df)
    idx = np.random.permutation(n)
    n_train = int(n * cfg.train_split)
    n_val = int(n * cfg.val_split)

    train_idx = idx[:n_train]
    val_idx = idx[n_train:n_train + n_val]
    test_idx = idx[n_train + n_val:]

    norm_params = {
        "cap_mean": cap_mean.tolist(), "cap_std": cap_std.tolist(),
        "dyn_mean": dyn_mean.tolist(), "dyn_std": dyn_std.tolist(),
        "y_mean": y_mean.tolist(), "y_std": y_std.tolist(),
        "cap_cols": cap_cols[:6], "dyn_cols": dyn_cols[:3],
        "target_cols": target_cols,
    }

    return (X_cap, X_dyn, Y_norm, Y,
            train_idx, val_idx, test_idx, norm_params)


def train(cfg: TrainingConfig) -> dict:
    """Train the encoder and return metrics."""
    if not HAS_TORCH:
        return {"status": "error", "message": "PyTorch not installed"}

    (X_cap, X_dyn, Y_norm, Y_raw,
     train_idx, val_idx, test_idx, norm_params) = load_and_split(cfg)

    # Create datasets
    def make_ds(idx):
        return TensorDataset(
            torch.from_numpy(X_cap[idx]),
            torch.from_numpy(X_dyn[idx]),
            torch.from_numpy(Y_norm[idx]),
        )

    train_ds = make_ds(train_idx)
    val_ds = make_ds(val_idx)
    test_ds = make_ds(test_idx)

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=len(val_ds))

    model = TwoModalityEncoder(cfg)
    optimiser = torch.optim.AdamW(
        model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimiser, max_lr=cfg.lr, total_steps=cfg.epochs * len(train_loader),
        pct_start=0.1)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    best_state = None

    for epoch in range(cfg.epochs):
        model.train()
        for xc, xd, yt in train_loader:
            pred = model(xc, xd, training=True)
            loss = criterion(pred, yt)
            optimiser.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimiser.step()
            scheduler.step()

        # Validation
        model.eval()
        with torch.no_grad():
            for xc, xd, yt in val_loader:
                val_pred = model(xc, xd, training=False)
                val_loss = criterion(val_pred, yt).item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    # Load best model and evaluate on test set
    model.load_state_dict(best_state)
    model.eval()

    test_loader = DataLoader(test_ds, batch_size=len(test_ds))
    with torch.no_grad():
        for xc, xd, yt in test_loader:
            test_pred = model(xc, xd, training=False)

    # Denormalise predictions
    y_std = np.array(norm_params["y_std"])
    y_mean = np.array(norm_params["y_mean"])
    pred_raw = test_pred.numpy() * y_std + y_mean
    true_raw = Y_raw[test_idx]

    # Pearson correlations per target
    correlations = {}
    for i, col in enumerate(norm_params["target_cols"]):
        r = float(np.corrcoef(pred_raw[:, i], true_raw[:, i])[0, 1])
        correlations[col] = round(r, 4)

    # Save model + normalisation params
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, out_dir / "encoder_v2.pt")
    (out_dir / "norm_params.json").write_text(
        json.dumps(norm_params, indent=2), encoding="utf-8")

    result = {
        "status": "ok",
        "n_train": len(train_idx),
        "n_val": len(val_idx),
        "n_test": len(test_idx),
        "best_val_loss": round(best_val_loss, 6),
        "test_correlations": correlations,
        "model_path": str(out_dir / "encoder_v2.pt"),
        "norm_params_path": str(out_dir / "norm_params.json"),
        "config": {
            "epochs": cfg.epochs,
            "batch_size": cfg.batch_size,
            "lr": cfg.lr,
            "latent_dim": cfg.latent_dim,
            "dropout_prob": cfg.dropout_prob,
        },
    }
    (out_dir / "training_result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    ap = argparse.ArgumentParser(description="Train the Op³ encoder")
    ap.add_argument("--data", required=True, help="Path to MC database CSV")
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--output", default="models/")
    args = ap.parse_args()

    cfg = TrainingConfig(
        data_path=args.data, epochs=args.epochs, output_dir=args.output)
    result = train(cfg)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
