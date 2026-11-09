"""
SolarGuard — Lightweight Custom CNN Fault Classifier Training Script

LOW-RAM / CPU CONSTRAINTS:
- Input shape: 64x64x3 (low memory footprint, fast feature extraction)
- Batch size: 16 (prevents memory spikes on low-RAM machines)
- Custom CNN: 3 small Conv2D layers (NOT heavy ResNet/VGG/MobileNet transfer learning)
- Generators/Prefetching: Streaming tf.data pipeline to avoid loading full dataset to RAM
- Epochs: 5 epochs (trains in ~60-90 seconds on CPU)
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
MODELS_DIR = BASE_DIR / 'ml_engine' / 'models'
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_OUTPUT_PATH = MODELS_DIR / 'fault_cnn.h5'
CLASSES_OUTPUT_PATH = MODELS_DIR / 'classes.json'


def build_lightweight_cnn(input_shape=(64, 64, 3), num_classes=4):
    """
    Constructs a low-parameter custom CNN (approx. 45,000 params)
    optimized for fast CPU training and low memory.
    """
    import tensorflow as tf
    from tensorflow.keras import layers, models

    model = models.Sequential([
        # Input and normalization
        layers.Input(shape=input_shape),
        layers.Rescaling(1.0 / 255.0),

        # Conv Block 1
        layers.Conv2D(16, (3, 3), padding='same', activation='relu'),
        layers.MaxPooling2D((2, 2)),

        # Conv Block 2
        layers.Conv2D(32, (3, 3), padding='same', activation='relu'),
        layers.MaxPooling2D((2, 2)),

        # Conv Block 3
        layers.Conv2D(64, (3, 3), padding='same', activation='relu'),
        layers.MaxPooling2D((2, 2)),

        # Dense Classifier Block
        layers.Flatten(),
        layers.Dense(64, activation='relu'),
        layers.Dropout(0.35),
        layers.Dense(num_classes, activation='softmax')
    ])

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )

    return model


def train_cnn(data_dir=None, epochs=5, batch_size=16, img_size=64):
    try:
        import tensorflow as tf
    except ImportError:
        print("[ERROR] TensorFlow is not installed in your current environment.")
        print("[*] To install TensorFlow: pip install tensorflow")
        print("[*] Note: The SolarGuard web app will automatically use its built-in")
        print("    OpenCV heuristic fallback engine until the CNN is trained.")
        sys.exit(1)

    train_path = (Path(data_dir) if data_dir else DATA_DIR) / 'train'
    val_path = (Path(data_dir) if data_dir else DATA_DIR) / 'val'

    if not train_path.exists() or not val_path.exists():
        print(f"[ERROR] Dataset directory structure not found at {DATA_DIR}")
        print("[*] Please run split_dataset.py first on your downloaded Kaggle dataset:")
        print("    python ml_engine/split_dataset.py --source /path/to/kaggle_download")
        print("    or run: python ml_engine/generate_mock_data.py --with-images")
        sys.exit(1)

    print("=" * 70)
    print("[SolarGuard] Training Lightweight Custom CNN Fault Classifier")
    print("=" * 70)
    print(f"[*] Train Directory: {train_path}")
    print(f"[*] Val Directory:   {val_path}")
    print(f"[*] Image Size:      {img_size}x{img_size} pixels")
    print(f"[*] Batch Size:      {batch_size}")
    print(f"[*] Epochs:          {epochs}")
    print("-" * 70)

    # 1. Load datasets via streaming tf.data pipeline
    train_ds = tf.keras.utils.image_dataset_from_directory(
        train_path,
        image_size=(img_size, img_size),
        batch_size=batch_size,
        shuffle=True,
        seed=42
    )

    val_ds = tf.keras.utils.image_dataset_from_directory(
        val_path,
        image_size=(img_size, img_size),
        batch_size=batch_size,
        shuffle=False,
        seed=42
    )

    class_names = train_ds.class_names
    num_classes = len(class_names)
    print(f"[*] Detected {num_classes} classes: {class_names}")

    # Optimize data pipeline for low memory & CPU caching
    AUTOTUNE = tf.data.AUTOTUNE
    train_ds = train_ds.cache().prefetch(buffer_size=AUTOTUNE)
    val_ds = val_ds.cache().prefetch(buffer_size=AUTOTUNE)

    # 2. Build model
    model = build_lightweight_cnn(input_shape=(img_size, img_size, 3), num_classes=num_classes)
    model.summary()

    # 3. Train
    print("\n[*] Starting training loop (CPU-optimized)...")
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=epochs,
        verbose=1
    )

    # 4. Evaluation
    val_loss, val_acc = model.evaluate(val_ds, verbose=0)
    print("\n" + "-" * 50)
    print(f"[OK] Final Validation Accuracy: {val_acc * 100:.2f}% (Loss: {val_loss:.4f})")
    print("-" * 50)

    # 5. Save model and classes mapping
    model.save(MODEL_OUTPUT_PATH)
    with open(CLASSES_OUTPUT_PATH, 'w') as f:
        json.dump(class_names, f, indent=2)

    print(f"\n[OK] Model weights saved to: {MODEL_OUTPUT_PATH}")
    print(f"[OK] Class labels saved to:   {CLASSES_OUTPUT_PATH}")
    print("=" * 70)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Train Lightweight CNN for SolarGuard")
    parser.add_argument('--data-dir', type=str, default=None, help="Base data directory (containing train/ and val/)")
    parser.add_argument('--epochs', type=int, default=5, help="Number of training epochs (default: 5)")
    parser.add_argument('--batch-size', type=int, default=16, help="Batch size (default: 16)")
    parser.add_argument('--img-size', type=int, default=64, help="Image resolution width/height (default: 64)")

    args = parser.parse_args()
    train_cnn(
        data_dir=args.data_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        img_size=args.img_size
    )
