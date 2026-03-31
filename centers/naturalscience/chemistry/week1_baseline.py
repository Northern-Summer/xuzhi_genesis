#!/usr/bin/env python3
"""
Week 1 Baseline: End-to-End Reaction Classification
USPTO-50k → Morgan Fingerprints → 2-Layer MLP → 10-Class Prediction

Completion Criteria:
- End-to-end runnable: python week1_baseline.py
- Reproducible: fixed random seed
- Metrics: accuracy, per-class precision/recall, latency, memory
- Constraints: <30min runtime, <2GB RAM
"""

import os
import json
import time
import random
import psutil
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

# RDKit
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')  # Suppress RDKit warnings

# Reproducibility
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
torch.manual_seed(RANDOM_SEED)

# Configuration
CONFIG = {
    "data_path": "/home/summer/xuzhi_genesis/centers/naturalscience/chemistry/data/uspto50k_train.csv",
    "fp_radius": 2,
    "fp_bits": 2048,
    "hidden_dim": 128,
    "batch_size": 64,
    "epochs": 10,
    "lr": 0.001,
    "sample_size": 5000,  # Use subset for speed
    "random_seed": RANDOM_SEED
}

def log_memory():
    """Return current memory usage in MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

class MoleculeDataset(Dataset):
    """Dataset for molecular fingerprints"""
    def __init__(self, smiles_list, labels, fp_radius=2, fp_bits=2048):
        self.smiles_list = smiles_list
        self.labels = labels
        self.fp_radius = fp_radius
        self.fp_bits = fp_bits
        self.fingerprints = []
        self.valid_indices = []
        
        print(f"[INFO] Generating Morgan fingerprints for {len(smiles_list)} molecules...")
        start_time = time.time()
        
        for idx, smiles in enumerate(smiles_list):
            if idx % 1000 == 0:
                print(f"  Progress: {idx}/{len(smiles_list)}")
            
            try:
                mol = Chem.MolFromSmiles(smiles)
                if mol:
                    fp = AllChem.GetMorganFingerprintAsBitVect(
                        mol, self.fp_radius, nBits=self.fp_bits
                    )
                    fp_array = np.array(fp)
                    self.fingerprints.append(fp_array)
                    self.valid_indices.append(idx)
                else:
                    self.fingerprints.append(np.zeros(fp_bits))
                    self.valid_indices.append(idx)
            except:
                self.fingerprints.append(np.zeros(fp_bits))
                self.valid_indices.append(idx)
        
        elapsed = time.time() - start_time
        print(f"[INFO] Fingerprint generation: {elapsed:.1f}s")
    
    def __len__(self):
        return len(self.fingerprints)
    
    def __getitem__(self, idx):
        return (
            torch.FloatTensor(self.fingerprints[idx]),
            torch.LongTensor([self.labels[idx]])[0]
        )

class SimpleMLP(nn.Module):
    """2-Layer MLP for reaction class prediction"""
    def __init__(self, input_dim, hidden_dim, num_classes):
        super(SimpleMLP, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(hidden_dim, num_classes)
    
    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        return x

def train_epoch(model, dataloader, criterion, optimizer, device):
    """Train for one epoch"""
    model.train()
    total_loss = 0
    correct = 0
    total = 0
    
    for batch_idx, (data, target) in enumerate(dataloader):
        data, target = data.to(device), target.to(device)
        
        optimizer.zero_grad()
        output = model(data)
        loss = criterion(output, target)
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
        pred = output.argmax(dim=1)
        correct += pred.eq(target).sum().item()
        total += target.size(0)
    
    avg_loss = total_loss / len(dataloader)
    accuracy = 100. * correct / total
    return avg_loss, accuracy

def evaluate(model, dataloader, device):
    """Evaluate model"""
    model.eval()
    all_preds = []
    all_targets = []
    inference_times = []
    
    with torch.no_grad():
        for data, target in dataloader:
            data = data.to(device)
            
            # Measure inference time
            start = time.time()
            output = model(data)
            inference_times.append(time.time() - start)
            
            pred = output.argmax(dim=1)
            all_preds.extend(pred.cpu().numpy())
            all_targets.extend(target.numpy())
    
    return np.array(all_preds), np.array(all_targets), inference_times

def main():
    print("="*60)
    print("Week 1 Baseline: Reaction Class Prediction")
    print("="*60)
    
    # Record start time and memory
    start_time = time.time()
    start_memory = log_memory()
    print(f"[INFO] Start memory: {start_memory:.1f} MB")
    
    # Load data
    print(f"\n[1/5] Loading data from {CONFIG['data_path']}...")
    df = pd.read_csv(CONFIG['data_path'])
    print(f"[INFO] Loaded {len(df)} samples")
    
    # Sample for faster training
    if CONFIG['sample_size'] < len(df):
        df = df.sample(n=CONFIG['sample_size'], random_state=RANDOM_SEED)
        print(f"[INFO] Sampled {CONFIG['sample_size']} samples for training")
    
    # Prepare data
    smiles_list = df['prod_smiles'].tolist()
    labels = df['class'].tolist()
    
    # Adjust labels to 0-indexed
    unique_classes = sorted(set(labels))
    class_map = {c: i for i, c in enumerate(unique_classes)}
    labels = [class_map[l] for l in labels]
    num_classes = len(unique_classes)
    
    print(f"[INFO] Number of classes: {num_classes}")
    print(f"[INFO] Class distribution: {pd.Series(labels).value_counts().to_dict()}")
    
    # Split data
    smiles_train, smiles_val, labels_train, labels_val = train_test_split(
        smiles_list, labels, test_size=0.2, random_state=RANDOM_SEED, stratify=labels
    )
    
    # Create datasets
    print("\n[2/5] Creating datasets...")
    train_dataset = MoleculeDataset(smiles_train, labels_train, 
                                    CONFIG['fp_radius'], CONFIG['fp_bits'])
    val_dataset = MoleculeDataset(smiles_val, labels_val,
                                  CONFIG['fp_radius'], CONFIG['fp_bits'])
    
    train_loader = DataLoader(train_dataset, batch_size=CONFIG['batch_size'], 
                              shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=CONFIG['batch_size'],
                           shuffle=False, num_workers=0)
    
    # Setup model
    print("\n[3/5] Setting up model...")
    device = torch.device('cpu')  # Force CPU
    model = SimpleMLP(CONFIG['fp_bits'], CONFIG['hidden_dim'], num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=CONFIG['lr'])
    
    print(f"[INFO] Model parameters: {sum(p.numel() for p in model.parameters())}")
    
    # Training
    print("\n[4/5] Training...")
    train_losses = []
    train_accs = []
    
    for epoch in range(CONFIG['epochs']):
        loss, acc = train_epoch(model, train_loader, criterion, optimizer, device)
        train_losses.append(loss)
        train_accs.append(acc)
        if epoch % 2 == 0:
            print(f"  Epoch {epoch}: Loss={loss:.4f}, Acc={acc:.2f}%")
    
    # Evaluation
    print("\n[5/5] Evaluating...")
    preds, targets, inference_times = evaluate(model, val_loader, device)
    
    # Calculate metrics
    accuracy = accuracy_score(targets, preds)
    precision, recall, f1, _ = precision_recall_fscore_support(
        targets, preds, average='macro', zero_division=0
    )
    per_class_precision, per_class_recall, _, _ = precision_recall_fscore_support(
        targets, preds, average=None, zero_division=0
    )
    cm = confusion_matrix(targets, preds)
    
    avg_inference_time = np.mean(inference_times) * 1000  # Convert to ms
    max_memory = log_memory()
    total_time = time.time() - start_time
    
    # Compile results
    results = {
        "config": CONFIG,
        "metrics": {
            "accuracy": float(accuracy),
            "macro_precision": float(precision),
            "macro_recall": float(recall),
            "macro_f1": float(f1),
            "per_class_precision": per_class_precision.tolist(),
            "per_class_recall": per_class_recall.tolist(),
        },
        "efficiency": {
            "avg_inference_time_ms": float(avg_inference_time),
            "max_memory_mb": float(max_memory),
            "total_runtime_sec": float(total_time),
        },
        "training_history": {
            "losses": train_losses,
            "accuracies": train_accs
        },
        "confusion_matrix": cm.tolist(),
        "class_distribution": pd.Series(labels).value_counts().to_dict()
    }
    
    # Save results
    output_dir = "/home/summer/xuzhi_genesis/centers/naturalscience/chemistry/results"
    os.makedirs(output_dir, exist_ok=True)
    
    results_path = os.path.join(output_dir, "week1_results.json")
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("\n" + "="*60)
    print("RESULTS SUMMARY")
    print("="*60)
    print(f"Accuracy: {accuracy*100:.2f}% (Random baseline: {100/num_classes:.1f}%)")
    print(f"Macro Precision: {precision:.3f}")
    print(f"Macro Recall: {recall:.3f}")
    print(f"Macro F1: {f1:.3f}")
    print(f"\nEfficiency:")
    print(f"  Avg inference time: {avg_inference_time:.2f} ms")
    print(f"  Max memory: {max_memory:.1f} MB")
    print(f"  Total runtime: {total_time:.1f} sec")
    print(f"\nResults saved to: {results_path}")
    print("="*60)
    
    return results

if __name__ == "__main__":
    results = main()
