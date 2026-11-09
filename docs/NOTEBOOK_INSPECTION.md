# SolarGuard Model Training Notebook Audit

## Cell 00 [code]

```python
from google.colab import drive
drive.mount('/content/drive')
```

**Outputs:**

```
Drive already mounted at /content/drive; to attempt to forcibly remount, call drive.mount("/content/drive", force_remount=True).

```

## Cell 01 [code]

```python
import os
import zipfile

print("1. Files in /content:")
print(os.listdir("/content"))

print("\n2. Dataset folder exists:")
print(os.path.exists("/content/solar_dataset"))

print("\n3. Google Drive connected:")
print(os.path.exists("/content/drive/MyDrive"))

print("\n4. ZIP file exists in Drive:")
zip_path = "/content/drive/MyDrive/archive.zip"
print(os.path.exists(zip_path))

if os.path.exists(zip_path):
    print("ZIP size:", round(os.path.getsize(zip_path) / 1024**2, 2), "MB")
    print("Valid ZIP:", zipfile.is_zipfile(zip_path))
```

**Outputs:**

```
1. Files in /content:
['.config', 'drive', 'solar_dataset', 'sample_data']

2. Dataset folder exists:
True

3. Google Drive connected:
True

4. ZIP file exists in Drive:
False

```

## Cell 02 [code]

```python
import os

dataset_path = "/content/solar_dataset"

for root, dirs, files in os.walk(dataset_path):
    depth = root.replace(dataset_path, "").count(os.sep)

    if depth > 2:
        continue

    images = [
        f for f in files
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ]

    print("  " * depth + os.path.basename(root) + "/")
    print("  " * depth + f"Images: {len(images)}")
```

**Outputs:**

```
solar_dataset/
Images: 0
  Faulty_solar_panel/
  Images: 0
    Bird-drop/
    Images: 191
    Dusty/
    Images: 190
    Physical-Damage/
    Images: 69
    Electrical-damage/
    Images: 103
    Clean/
    Images: 193
    Snow-Covered/
    Images: 123

```

## Cell 03 [code]

```python
import os

drive_path = "/content/drive/MyDrive"

print("Searching Google Drive for ZIP files...\n")

found = []

for root, dirs, files in os.walk(drive_path):
    for file in files:
        if file.lower().endswith(".zip"):
            full_path = os.path.join(root, file)
            found.append(full_path)
            print(full_path)

if not found:
    print("No ZIP files found in MyDrive.")
```

**Outputs:**

```
Searching Google Drive for ZIP files...

/content/drive/MyDrive/archive (3).zip
/content/drive/MyDrive/nutrition-tracker.zip
/content/drive/MyDrive/solarguard_phase1_2.zip
/content/drive/MyDrive/Beh Project Quishing.zip
/content/drive/MyDrive/archive (1).zip

```

## Cell 04 [code]

```python
import os
import zipfile

for name in ["archive (3).zip", "archive (1).zip"]:
    path = f"/content/drive/MyDrive/{name}"

    print(f"\nFile: {name}")
    print("Size (MB):", round(os.path.getsize(path) / 1024**2, 2))
    print("Valid ZIP:", zipfile.is_zipfile(path))

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            print("First 10 entries:")
            for item in z.namelist()[:10]:
                print(" ", item)
```

**Outputs:**

```

File: archive (3).zip
Size (MB): 0.0
Valid ZIP: True
First 10 entries:
  Multiclass Diabetes Dataset/Multiclass Diabetes Dataset.csv

File: archive (1).zip
Size (MB): 304.93
Valid ZIP: True
First 10 entries:
  Faulty_solar_panel/Bird-drop/Bird (1).jpeg
  Faulty_solar_panel/Bird-drop/Bird (10).jpg
  Faulty_solar_panel/Bird-drop/Bird (100).jpg
  Faulty_solar_panel/Bird-drop/Bird (101).jpg
  Faulty_solar_panel/Bird-drop/Bird (102).jpg
  Faulty_solar_panel/Bird-drop/Bird (103).jpg
  Faulty_solar_panel/Bird-drop/Bird (104).jpg
  Faulty_solar_panel/Bird-drop/Bird (105).jpg
  Faulty_solar_panel/Bird-drop/Bird (106).jpg
  Faulty_solar_panel/Bird-drop/Bird (107).jpg

```

## Cell 05 [code]

```python
import os
import zipfile

zip_path = "/content/drive/MyDrive/archive (1).zip"
extract_path = "/content/solar_dataset"

os.makedirs(extract_path, exist_ok=True)

with zipfile.ZipFile(zip_path, "r") as z:
    z.extractall(extract_path)

print("Extraction completed!")
print("Folders:", os.listdir(extract_path))
```

**Outputs:**

```
Extraction completed!
Folders: ['Faulty_solar_panel']

```

## Cell 06 [code]

```python
import os

dataset_path = "/content/solar_dataset"

for root, dirs, files in os.walk(dataset_path):
    images = [
        f for f in files
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ]

    if images:
        print(
            os.path.relpath(root, dataset_path),
            "→",
            len(images),
            "images"
        )
```

**Outputs:**

```
Faulty_solar_panel/Bird-drop → 191 images
Faulty_solar_panel/Bird-drop/New → 16 images
Faulty_solar_panel/Dusty → 190 images
Faulty_solar_panel/Physical-Damage → 69 images
Faulty_solar_panel/Electrical-damage → 103 images
Faulty_solar_panel/Clean → 193 images
Faulty_solar_panel/Snow-Covered → 123 images

```

## Cell 07 [code]

```python
import os
import random
import matplotlib.pyplot as plt
from PIL import Image

base = "/content/solar_dataset/Faulty_solar_panel"

classes = {
    "Normal": "Clean",
    "Dusty": "Dusty",
    "Bird-Dropping": "Bird-drop",
    "Surface-Damage": "Physical-Damage"
}

fig, axes = plt.subplots(4, 5, figsize=(15, 11))

random.seed(42)

for row, (label, folder) in enumerate(classes.items()):
    folder_path = os.path.join(base, folder)

    images = []

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                images.append(os.path.join(root, file))

    selected = random.sample(images, min(5, len(images)))

    for col in range(5):
        ax = axes[row, col]
        ax.axis("off")

        if col < len(selected):
            try:
                with Image.open(selected[col]) as img:
                    ax.imshow(img.convert("RGB"))
            except Exception as e:
                ax.text(0.5, 0.5, "Image error", ha="center")

        if col == 0:
            ax.set_title(label, fontsize=12, fontweight="bold")

plt.tight_layout()
plt.show()
```

**Outputs:**

```
<Figure size 1500x1100 with 20 Axes>
```

## Cell 08 [code]

```python
import os
import random
import shutil
from pathlib import Path
from collections import Counter

random.seed(42)

source = Path("/content/solar_dataset/Faulty_solar_panel")
destination = Path("/content/solarguard_split")

class_map = {
    "Normal": "Clean",
    "Dusty": "Dusty",
    "Bird-Dropping": "Bird-drop",
    "Surface-Damage": "Physical-Damage"
}

extensions = {".jpg", ".jpeg", ".png", ".webp"}

if destination.exists():
    shutil.rmtree(destination)

for label, folder in class_map.items():
    files = [
        p for p in (source / folder).rglob("*")
        if p.is_file() and p.suffix.lower() in extensions
    ]

    random.shuffle(files)

    n = len(files)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    splits = {
        "train": files[:train_end],
        "val": files[train_end:val_end],
        "test": files[val_end:]
    }

    for split_name, paths in splits.items():
        target = destination / split_name / label
        target.mkdir(parents=True, exist_ok=True)

        for i, path in enumerate(paths):
            shutil.copy2(path, target / f"{i:04d}{path.suffix.lower()}")

    print(
        f"{label}: "
        f"train={len(splits['train'])}, "
        f"val={len(splits['val'])}, "
        f"test={len(splits['test'])}"
    )

print("\nDataset preparation complete!")
```

**Outputs:**

```
Normal: train=135, val=29, test=29
Dusty: train=133, val=28, test=29
Bird-Dropping: train=144, val=31, test=32
Surface-Damage: train=48, val=10, test=11

Dataset preparation complete!

```

## Cell 09 [code]

```python
import tensorflow as tf

print("TensorFlow version:", tf.__version__)
print("Available GPUs:", tf.config.list_physical_devices("GPU"))
```

**Outputs:**

```
TensorFlow version: 2.21.0
Available GPUs: [PhysicalDevice(name='/physical_device:GPU:0', device_type='GPU')]

```

## Cell 10 [markdown]

Model Training Code

## Cell 11 [code]

```python
import tensorflow as tf
import numpy as np
from pathlib import Path

DATA_DIR = "/content/solarguard_split"
IMG_SIZE = (224, 224)
BATCH_SIZE = 16
SEED = 42

train_ds = tf.keras.utils.image_dataset_from_directory(
    f"{DATA_DIR}/train",
    image_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    label_mode="int",
    shuffle=True,
    seed=SEED
)

val_ds = tf.keras.utils.image_dataset_from_directory(
    f"{DATA_DIR}/val",
    image_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    label_mode="int",
    shuffle=False
)

class_names = train_ds.class_names
print("Classes:", class_names)
```

**Outputs:**

```
Found 460 files belonging to 4 classes.
Found 98 files belonging to 4 classes.
Classes: ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage']

```

## Cell 12 [code]

```python
from tensorflow.keras import layers, Model
from tensorflow.keras.applications import MobileNetV2

augmentation = tf.keras.Sequential([
    layers.RandomFlip("horizontal"),
    layers.RandomRotation(0.08),
    layers.RandomZoom(0.10),
    layers.RandomContrast(0.10)
], name="augmentation")

base_model = MobileNetV2(
    input_shape=(224, 224, 3),
    include_top=False,
    weights="imagenet"
)

base_model.trainable = False

inputs = layers.Input(shape=(224, 224, 3))

x = augmentation(inputs)
x = layers.Rescaling(1.0 / 127.5, offset=-1)(x)

x = base_model(x, training=False)
x = layers.GlobalAveragePooling2D()(x)
x = layers.Dropout(0.3)(x)

outputs = layers.Dense(
    len(class_names),
    activation="softmax"
)(x)

model = Model(inputs, outputs)

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"]
)

model.summary()
```

**Outputs:**

```
Downloading data from https://storage.googleapis.com/tensorflow/keras-applications/mobilenet_v2/mobilenet_v2_weights_tf_dim_ordering_tf_kernels_1.0_224_no_top.h5
[1m9406464/9406464[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m0s[0m 0us/step
[1mModel: "functional_1"[0m
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃[1m [0m[1mLayer (type)                   [0m[1m [0m┃[1m [0m[1mOutput Shape          [0m[1m [0m┃[1m [0m[1m      Param #[0m[1m [0m┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ input_layer_1 ([38;5;33mInputLayer[0m)      │ ([38;5;45mNone[0m, [38;5;34m224[0m, [38;5;34m224[0m, [38;5;34m3[0m)    │             [38;5;34m0[0m │
├─────────────────────────────────┼────────────────────────┼───────────────┤
│ augmentation ([38;5;33mSequential[0m)       │ ([38;5;45mNone[0m, [38;5;34m224[0m, [38;5;34m224[0m, [38;5;34m3[0m)    │             [38;5;34m0[0m │
├─────────────────────────────────┼────────────────────────┼───────────────┤
│ rescaling ([38;5;33mRescaling[0m)           │ ([38;5;45mNone[0m, [38;5;34m224[0m, [38;5;34m224[0m, [38;5;34m3[0m)    │             [38;5;34m0[0m │
├─────────────────────────────────┼────────────────────────┼───────────────┤
│ mobilenetv2_1.00_224            │ ([38;5;45mNone[0m, [38;5;34m7[0m, [38;5;34m7[0m, [38;5;34m1280[0m)     │     [38;5;34m2,257,984[0m │
│ ([38;5;33mFunctional[0m)                    │                        │               │
├─────────────────────────────────┼────────────────────────┼───────────────┤
│ global_average_pooling2d        │ ([38;5;45mNone[0m, [38;5;34m1280[0m)           │             [38;5;34m0[0m │
│ ([38;5;33mGlobalAveragePooling2D[0m)        │                        │               │
├─────────────────────────────────┼────────────────────────┼───────────────┤
│ dropout ([38;5;33mDropout[0m)               │ ([38;5;45mNone[0m, [38;5;34m1280[0m)           │             [38;5;34m0[0m │
├─────────────────────────────────┼────────────────────────┼───────────────┤
│ dense ([38;5;33mDense[0m)                   │ ([38;5;45mNone[0m, [38;5;34m4[0m)              │         [38;5;34m5,124[0m │
└─────────────────────────────────┴────────────────────────┴───────────────┘
[1m Total params: [0m[38;5;34m2,263,108[0m (8.63 MB)
[1m Trainable params: [0m[38;5;34m5,124[0m (20.02 KB)
[1m Non-trainable params: [0m[38;5;34m2,257,984[0m (8.61 MB)

```

## Cell 13 [code]

```python
from sklearn.utils.class_weight import compute_class_weight

train_labels = np.concatenate([
    labels.numpy()
    for images, labels in train_ds
])

weights = compute_class_weight(
    class_weight="balanced",
    classes=np.arange(len(class_names)),
    y=train_labels
)

class_weights = {
    i: float(weight)
    for i, weight in enumerate(weights)
}

print("Class weights:")
for i, name in enumerate(class_names):
    print(name, ":", round(class_weights[i], 3))
```

**Outputs:**

```
Class weights:
Bird-Dropping : 0.799
Dusty : 0.865
Normal : 0.852
Surface-Damage : 2.396

```

## Cell 14 [code]

```python
callbacks = [
    tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=4,
        restore_best_weights=True
    ),
    tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=2,
        min_lr=1e-6
    )
]

history = model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=15,
    class_weight=class_weights,
    callbacks=callbacks
)
```

**Outputs:**

```
Epoch 1/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m17s[0m 249ms/step - accuracy: 0.2891 - loss: 1.7117 - val_accuracy: 0.4490 - val_loss: 1.2083 - learning_rate: 0.0010
Epoch 2/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 224ms/step - accuracy: 0.5283 - loss: 1.1391 - val_accuracy: 0.6122 - val_loss: 0.9807 - learning_rate: 0.0010
Epoch 3/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m6s[0m 225ms/step - accuracy: 0.5935 - loss: 0.8950 - val_accuracy: 0.6939 - val_loss: 0.8225 - learning_rate: 0.0010
Epoch 4/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 237ms/step - accuracy: 0.6630 - loss: 0.8516 - val_accuracy: 0.6327 - val_loss: 0.8199 - learning_rate: 0.0010
Epoch 5/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 217ms/step - accuracy: 0.6848 - loss: 0.7870 - val_accuracy: 0.7551 - val_loss: 0.7195 - learning_rate: 0.0010
Epoch 6/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m6s[0m 217ms/step - accuracy: 0.6761 - loss: 0.7079 - val_accuracy: 0.7449 - val_loss: 0.7022 - learning_rate: 0.0010
Epoch 7/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 219ms/step - accuracy: 0.7717 - loss: 0.6088 - val_accuracy: 0.7755 - val_loss: 0.6852 - learning_rate: 0.0010
Epoch 8/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m10s[0m 234ms/step - accuracy: 0.7652 - loss: 0.5659 - val_accuracy: 0.7245 - val_loss: 0.6887 - learning_rate: 0.0010
Epoch 9/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m10s[0m 240ms/step - accuracy: 0.7543 - loss: 0.5637 - val_accuracy: 0.7755 - val_loss: 0.6616 - learning_rate: 0.0010
Epoch 10/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m6s[0m 222ms/step - accuracy: 0.8043 - loss: 0.5311 - val_accuracy: 0.7755 - val_loss: 0.6658 - learning_rate: 0.0010
Epoch 11/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m10s[0m 224ms/step - accuracy: 0.7848 - loss: 0.5065 - val_accuracy: 0.7755 - val_loss: 0.6593 - learning_rate: 0.0010
Epoch 12/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 224ms/step - accuracy: 0.8174 - loss: 0.4982 - val_accuracy: 0.7959 - val_loss: 0.6512 - learning_rate: 0.0010
Epoch 13/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 228ms/step - accuracy: 0.8217 - loss: 0.4576 - val_accuracy: 0.8061 - val_loss: 0.6642 - learning_rate: 0.0010
Epoch 14/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m10s[0m 216ms/step - accuracy: 0.8283 - loss: 0.4196 - val_accuracy: 0.7857 - val_loss: 0.6637 - learning_rate: 0.0010
Epoch 15/15
[1m29/29[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 226ms/step - accuracy: 0.7913 - loss: 0.5137 - val_accuracy: 0.7959 - val_loss: 0.6433 - learning_rate: 5.0000e-04

```

## Cell 15 [code]

```python
import tensorflow as tf
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
from sklearn.metrics import ConfusionMatrixDisplay

test_ds = tf.keras.utils.image_dataset_from_directory(
    "/content/solarguard_split/test",
    image_size=(224, 224),
    batch_size=16,
    label_mode="int",
    shuffle=False
)

test_loss, test_accuracy = model.evaluate(test_ds)

print(f"\nTEST ACCURACY: {test_accuracy * 100:.2f}%")

y_true = np.concatenate([
    labels.numpy() for images, labels in test_ds
])

predictions = model.predict(test_ds, verbose=0)
y_pred = np.argmax(predictions, axis=1)

print("\nCLASSIFICATION REPORT:")
print(classification_report(
    y_true,
    y_pred,
    labels=list(range(len(class_names))),
    target_names=class_names,
    zero_division=0
))

cm = confusion_matrix(
    y_true,
    y_pred,
    labels=list(range(len(class_names)))
)

disp = ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=class_names
)

fig, ax = plt.subplots(figsize=(9, 7))
disp.plot(ax=ax, cmap="Blues", xticks_rotation=30)
plt.title("SolarGuard CNN — Test Confusion Matrix")
plt.show()
```

**Outputs:**

```
Found 101 files belonging to 4 classes.
[1m7/7[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m3s[0m 393ms/step - accuracy: 0.8020 - loss: 0.6837

TEST ACCURACY: 80.20%

CLASSIFICATION REPORT:
                precision    recall  f1-score   support

 Bird-Dropping       0.74      0.72      0.73        32
         Dusty       0.86      0.86      0.86        29
        Normal       0.85      0.97      0.90        29
Surface-Damage       0.62      0.45      0.53        11

      accuracy                           0.80       101
     macro avg       0.77      0.75      0.76       101
  weighted avg       0.79      0.80      0.80       101

<Figure size 900x700 with 2 Axes>
```

## Cell 16 [code]

```python
import os
import json
import shutil

output_dir = "/content/drive/MyDrive/SolarGuard_Model"
os.makedirs(output_dir, exist_ok=True)

model_path = os.path.join(output_dir, "solarguard_model.keras")
model.save(model_path)

metadata = {
    "class_names": class_names,
    "image_size": [224, 224],
    "input_color_mode": "RGB",
    "input_pixel_range": [0, 255],
    "preprocessing": "Included inside model (MobileNetV2 Rescaling)",
    "model_type": "MobileNetV2 transfer learning",
    "training_status": "Initial experimental model"
}

with open(os.path.join(output_dir, "model_metadata.json"), "w") as f:
    json.dump(metadata, f, indent=2)

print("Model saved:", model_path)
print("Metadata saved:", os.path.join(output_dir, "model_metadata.json"))
```

**Outputs:**

```
Model saved: /content/drive/MyDrive/SolarGuard_Model/solarguard_model.keras
Metadata saved: /content/drive/MyDrive/SolarGuard_Model/model_metadata.json

```

## Cell 17 [code]

```python
import tensorflow as tf
import json
import os

from google.colab import drive
drive.mount("/content/drive")

model_dir = "/content/drive/MyDrive/SolarGuard_Model"

model = tf.keras.models.load_model(
    os.path.join(model_dir, "solarguard_model.keras"),
    compile=False
)

with open(os.path.join(model_dir, "model_metadata.json")) as f:
    metadata = json.load(f)

class_names = metadata["class_names"]

print("Model loaded successfully!")
print("Classes:", class_names)
print("MobileNetV2 layers found:",
      [layer.name for layer in model.layers
       if isinstance(layer, tf.keras.Model)])
```

**Outputs:**

```
Mounted at /content/drive
Model loaded successfully!
Classes: ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage']
MobileNetV2 layers found: ['augmentation', 'mobilenetv2_1.00_224']

```

## Cell 18 [code]

```python
import os
import zipfile

zip_path = "/content/drive/MyDrive/archive (1).zip"
extract_path = "/content/solar_dataset"

if not os.path.exists(extract_path):
    os.makedirs(extract_path, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_path)

    print("Dataset extracted successfully!")
else:
    print("Dataset already extracted.")

print("Dataset folders:", os.listdir(extract_path))
```

**Outputs:**

```
Dataset extracted successfully!
Dataset folders: ['Faulty_solar_panel']

```

## Cell 19 [code]

```python
import os

split_path = "/content/solarguard_split"

print("Training split exists:", os.path.exists(split_path))

if os.path.exists(split_path):
    for split in ["train", "val", "test"]:
        folder = os.path.join(split_path, split)

        count = sum(
            len(files)
            for _, _, files in os.walk(folder)
        )

        print(f"{split}: {count} files")
else:
    print("Training split needs to be restored.")
```

**Outputs:**

```
Training split exists: False
Training split needs to be restored.

```

## Cell 20 [code]

```python
import os
import zipfile

folder = "/content/drive/MyDrive/SolarGuard_Datasets"

print("Folder exists:", os.path.exists(folder))

if os.path.exists(folder):
    for filename in os.listdir(folder):
        path = os.path.join(folder, filename)

        if os.path.isfile(path):
            print("\nFile:", filename)
            print("Size (MB):", round(os.path.getsize(path) / 1024**2, 2))

            if filename.lower().endswith(".zip"):
                print("Valid ZIP:", zipfile.is_zipfile(path))

                if zipfile.is_zipfile(path):
                    with zipfile.ZipFile(path) as z:
                        print("First 20 entries:")
                        for name in z.namelist()[:20]:
                            print(" ", name)
```

**Outputs:**

```
Folder exists: True

File: Solar Panel Faulty Detection.v4i.yolov8.zip
Size (MB): 248.86
Valid ZIP: True
First 20 entries:
  README.dataset.txt
  README.roboflow.txt
  data.yaml
  test/
  test/images/
  test/images/1-102-_jpg.rf.5f8b08b27e5da0fca66f6f2d6fe9e546.jpg
  test/images/1-103-_jpg.rf.d498059c04ce9e493dd1956079d1fb94.jpg
  test/images/1-123-_jpg.rf.85f4ca546d73af85fe3050a382a43305.jpg
  test/images/1-2-_jpg.rf.c7342cae801e9470ac83a624e1492559.jpg
  test/images/1-34-_jpg.rf.3bc72c526529ec505cea1a6392947ad0.jpg
  test/images/1-4-_jpg.rf.8587869ab862660f734c32e82c1fae9d.jpg
  test/images/1-45-_jpg.rf.8de46df1bc123a4e19136f6f507b0953.jpg
  test/images/1-46-_jpg.rf.993f077b0bb94668607d68419e349fee.jpg
  test/images/1-50-_jpg.rf.0c8b9720a5c6e43255378cc35ad2dca0.jpg
  test/images/1-62-_jpg.rf.7ae38b8ff0223951fa1c761af4a830a0.jpg
  test/images/1-73-_jpg.rf.e33e71fe65ddeeb4b58317934400b28b.jpg
  test/images/1-74-_jpg.rf.1c539b6ef13e6f687d1ee72c0effe397.jpg
  test/images/1-75-_jpg.rf.51157be5991fd6f819d1ef248e61529d.jpg
  test/images/1-80-_jpg.rf.ebdc9397fb68cb8e3654c63551ed7c93.jpg
  test/images/1-83-_jpg.rf.fc2b371d8fc069b43b39a2eaec4bac4f.jpg

```

## Cell 21 [code]

```python
import os
import zipfile
import yaml
from collections import Counter

zip_path = (
    "/content/drive/MyDrive/SolarGuard_Datasets/"
    "Solar Panel Faulty Detection.v4i.yolov8.zip"
)

extract_path = "/content/solarguard_roboflow"

os.makedirs(extract_path, exist_ok=True)

with zipfile.ZipFile(zip_path, "r") as z:
    z.extractall(extract_path)

print("Dataset extracted successfully!\n")

# Read the YOLO dataset configuration
yaml_path = os.path.join(extract_path, "data.yaml")

with open(yaml_path, "r") as f:
    config = yaml.safe_load(f)

print("CLASS NAMES:")
print(config.get("names"))

print("\nDECLARED NUMBER OF CLASSES:")
print(config.get("nc"))

print("\nDATASET SPLITS:")

for split in ["train", "valid", "val", "test"]:
    images_dir = os.path.join(extract_path, split, "images")
    labels_dir = os.path.join(extract_path, split, "labels")

    if not os.path.isdir(images_dir):
        continue

    images = [
        f for f in os.listdir(images_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ]

    labels = [
        f for f in os.listdir(labels_dir)
        if f.endswith(".txt")
    ] if os.path.isdir(labels_dir) else []

    class_counts = Counter()
    empty_labels = 0

    for filename in labels:
        with open(os.path.join(labels_dir, filename), "r") as f:
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            empty_labels += 1

        for line in lines:
            parts = line.split()
            if parts:
                class_counts[int(parts[0])] += 1

    print(f"\n{split.upper()}")
    print("Images:", len(images))
    print("Label files:", len(labels))
    print("Empty label files:", empty_labels)
    print("Object annotations by class:", dict(class_counts))
```

**Outputs:**

```
Dataset extracted successfully!

CLASS NAMES:
['Bird Drop', 'Defective', 'Dust', 'Non Defective', 'Physical Damage', 'Snow']

DECLARED NUMBER OF CLASSES:
6

DATASET SPLITS:

TRAIN
Images: 2903
Label files: 2903
Empty label files: 0
Object annotations by class: {4: 1835, 1: 1632, 3: 1821, 2: 1753, 5: 1719, 0: 1753}

VALID
Images: 402
Label files: 402
Empty label files: 0
Object annotations by class: {3: 250, 1: 219, 4: 270, 2: 240, 5: 257, 0: 273}

TEST
Images: 331
Label files: 331
Empty label files: 0
Object annotations by class: {4: 197, 3: 202, 5: 209, 1: 239, 2: 192, 0: 191}

```

## Cell 22 [code]

```python
from collections import Counter, defaultdict
from pathlib import Path

base = Path("/content/solarguard_roboflow")

names = [
    "Bird Drop",
    "Defective",
    "Dust",
    "Non Defective",
    "Physical Damage",
    "Snow"
]

allowed = {0, 2, 3, 4}

for split in ["train", "valid", "test"]:
    label_dir = base / split / "labels"

    if not label_dir.exists():
        continue

    single_class = Counter()
    mixed_classes = Counter()
    excluded_only = 0
    invalid = 0

    for file in label_dir.glob("*.txt"):
        try:
            with open(file, "r") as f:
                ids = {
                    int(line.split()[0])
                    for line in f
                    if line.strip()
                }
        except (ValueError, IndexError):
            invalid += 1
            continue

        if not ids:
            invalid += 1
        elif len(ids) == 1 and next(iter(ids)) in allowed:
            single_class[next(iter(ids))] += 1
        elif ids.isdisjoint(allowed):
            excluded_only += 1
        else:
            mixed_classes[tuple(sorted(ids))] += 1

    print(f"\n{split.upper()}")
    print("Single-class usable images:")
    for class_id, count in sorted(single_class.items()):
        print(f"  {names[class_id]}: {count}")

    print("Total single-class:", sum(single_class.values()))
    print("Excluded-only:", excluded_only)
    print("Mixed-class images:", sum(mixed_classes.values()))
    print("Invalid/empty:", invalid)

    print("Most common mixed combinations:")
    for combo, count in mixed_classes.most_common(5):
        print(" ", [names[i] for i in combo], ":", count)
```

**Outputs:**

```

TRAIN
Single-class usable images:
  Bird Drop: 23
  Dust: 397
  Non Defective: 1381
  Physical Damage: 31
Total single-class: 1832
Excluded-only: 284
Mixed-class images: 787
Invalid/empty: 0
Most common mixed combinations:
  ['Defective', 'Dust'] : 420
  ['Defective', 'Physical Damage'] : 236
  ['Bird Drop', 'Defective'] : 64
  ['Defective', 'Non Defective', 'Snow'] : 19
  ['Defective', 'Non Defective', 'Physical Damage'] : 17

VALID
Single-class usable images:
  Dust: 53
  Non Defective: 179
  Physical Damage: 4
Total single-class: 236
Excluded-only: 38
Mixed-class images: 128
Invalid/empty: 0
Most common mixed combinations:
  ['Defective', 'Dust'] : 60
  ['Defective', 'Physical Damage'] : 40
  ['Bird Drop', 'Defective'] : 9
  ['Defective', 'Non Defective', 'Physical Damage'] : 6
  ['Bird Drop', 'Defective', 'Dust'] : 5

TEST
Single-class usable images:
  Dust: 6
  Non Defective: 157
  Physical Damage: 4
Total single-class: 167
Excluded-only: 29
Mixed-class images: 135
Invalid/empty: 0
Most common mixed combinations:
  ['Defective', 'Dust'] : 85
  ['Defective', 'Physical Damage'] : 27
  ['Defective', 'Non Defective', 'Physical Damage'] : 6
  ['Bird Drop', 'Defective'] : 6
  ['Defective', 'Dust', 'Non Defective'] : 3

```

## Cell 23 [code]

```python
from pathlib import Path
from collections import Counter

base = Path("/content/solarguard_roboflow")

class_map = {
    0: "Bird-Dropping",
    2: "Dusty",
    3: "Normal",
    4: "Surface-Damage"
}

generic_defective = 1

for split in ["train", "valid", "test"]:
    label_dir = base / split / "labels"

    counts = Counter()
    excluded = Counter()

    for file in label_dir.glob("*.txt"):
        with open(file, "r") as f:
            ids = {
                int(line.split()[0])
                for line in f
                if line.strip()
            }

        # Ignore generic "Defective" for candidate classification
        specific = ids - {generic_defective}

        if len(specific) == 1:
            class_id = next(iter(specific))

            if class_id in class_map:
                counts[class_map[class_id]] += 1
            else:
                excluded["Snow only"] += 1

        elif len(specific) == 0:
            excluded["Generic Defective only"] += 1
        else:
            excluded["Multiple specific classes"] += 1

    print(f"\n{split.upper()}")

    for name in class_map.values():
        print(f"{name}: {counts[name]}")

    print("Total candidate images:", sum(counts.values()))
    print("Excluded:", dict(excluded))
```

**Outputs:**

```

TRAIN
Bird-Dropping: 87
Dusty: 817
Normal: 1382
Surface-Damage: 267
Total candidate images: 2553
Excluded: {'Snow only': 280, 'Multiple specific classes': 66, 'Generic Defective only': 4}

VALID
Bird-Dropping: 9
Dusty: 113
Normal: 179
Surface-Damage: 44
Total candidate images: 345
Excluded: {'Multiple specific classes': 19, 'Snow only': 36, 'Generic Defective only': 2}

TEST
Bird-Dropping: 6
Dusty: 91
Normal: 159
Surface-Damage: 31
Total candidate images: 287
Excluded: {'Snow only': 29, 'Multiple specific classes': 15}

```

## Cell 24 [code]

```python
from pathlib import Path
from PIL import Image
import matplotlib.pyplot as plt
import random

base = Path("/content/solarguard_roboflow")
random.seed(42)

categories = {
    "Bird-Dropping": {0, 1},
    "Dusty": {1, 2},
    "Surface-Damage": {1, 4}
}

fig, axes = plt.subplots(3, 5, figsize=(16, 10))

for row, (category, expected_ids) in enumerate(categories.items()):
    candidates = []

    for label_file in (base / "train" / "labels").glob("*.txt"):
        with open(label_file) as f:
            ids = {
                int(line.split()[0])
                for line in f
                if line.strip()
            }

        if ids == expected_ids:
            image_dir = base / "train" / "images"

            for ext in [".jpg", ".jpeg", ".png", ".webp"]:
                image_path = image_dir / (label_file.stem + ext)

                if image_path.exists():
                    candidates.append(image_path)
                    break

    print(category, "candidate images:", len(candidates))

    selected = random.sample(candidates, min(5, len(candidates)))

    for col in range(5):
        ax = axes[row, col]
        ax.axis("off")

        if col < len(selected):
            with Image.open(selected[col]) as img:
                ax.imshow(img.convert("RGB"))

        if col == 0:
            ax.set_title(category, fontweight="bold")

plt.tight_layout()
plt.show()
```

**Outputs:**

```
Bird-Dropping candidate images: 64
Dusty candidate images: 420
Surface-Damage candidate images: 236
<Figure size 1600x1000 with 15 Axes>
```

## Cell 25 [code]

```python
from pathlib import Path
from PIL import Image, ImageOps
from collections import defaultdict
import hashlib
import io

base = Path("/content/solarguard_roboflow")

image_files = []

for split in ["train", "valid", "test"]:
    folder = base / split / "images"

    if folder.exists():
        image_files.extend([
            p for p in folder.iterdir()
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        ])

print("Total images:", len(image_files))

# Exact file duplicates
exact_groups = defaultdict(list)

# Same decoded pixels, even if files are encoded differently
pixel_groups = defaultdict(list)

for path in image_files:
    try:
        data = path.read_bytes()
        exact_hash = hashlib.sha256(data).hexdigest()
        exact_groups[exact_hash].append(path)

        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            pixel_hash = hashlib.sha256(
                img.size[0].to_bytes(4, "big") +
                img.size[1].to_bytes(4, "big") +
                img.tobytes()
            ).hexdigest()

        pixel_groups[pixel_hash].append(path)

    except Exception as e:
        print("Error reading:", path, e)

exact_duplicates = [
    group for group in exact_groups.values()
    if len(group) > 1
]

pixel_duplicates = [
    group for group in pixel_groups.values()
    if len(group) > 1
]

print("\nExact duplicate groups:", len(exact_duplicates))
print("Pixel-identical groups:", len(pixel_duplicates))

print("\nExamples of duplicate groups:")
for group in pixel_duplicates[:10]:
    for path in group:
        print(" ", path.relative_to(base))
    print("---")

cross_split = [
    group for group in pixel_duplicates
    if len({p.relative_to(base).parts[0] for p in group}) > 1
]

print("\nPixel-identical groups crossing dataset splits:", len(cross_split))
```

**Outputs:**

```
Total images: 3636

Exact duplicate groups: 4
Pixel-identical groups: 4

Examples of duplicate groups:
  train/images/IMG_20241003_093249_102_jpg.rf.00c0c2ff8e8a06a044a3246f1b13aa77.jpg
  train/images/IMG_20241003_093249_102_jpg.rf.14f4ca49127f3dabad7206b667c746d6.jpg
---
  train/images/2-37-_jpg.rf.e21ba5b5360fb1ff641f746d1e92e921.jpg
  test/images/2-37-_jpg.rf.11c764721408faf3f8c037a7df46511d.jpg
---
  train/images/2-115-_jpg.rf.abeb5c6555d1c2e6d1ed5ad7c69b6bfa.jpg
  train/images/2-115-_jpg.rf.05ac92c34077a86431452a03e2561f6e.jpg
---
  train/images/1-17-_jpg.rf.5ea89df0d6b9f12b1f7caf1a95072f3b.jpg
  train/images/Imgdirty_881_1_jpg.rf.e6a13a6e8d3074abe253f2a3b8af8858.jpg
---

Pixel-identical groups crossing dataset splits: 1

```

## Cell 26 [code]

```python
from pathlib import Path
from collections import defaultdict, Counter

base = Path("/content/solarguard_roboflow")

source_groups = defaultdict(list)

for split in ["train", "valid", "test"]:
    image_dir = base / split / "images"

    for path in image_dir.iterdir():
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue

        # Remove Roboflow's generated filename suffix
        source_id = path.name.split(".rf.")[0].lower()
        source_groups[source_id].append(path)

repeated = {
    key: paths
    for key, paths in source_groups.items()
    if len(paths) > 1
}

cross_split = {
    key: paths
    for key, paths in repeated.items()
    if len({
        p.relative_to(base).parts[0]
        for p in paths
    }) > 1
}

print("Total images:", sum(len(v) for v in source_groups.values()))
print("Unique filename-based source IDs:", len(source_groups))
print("Repeated source-ID groups:", len(repeated))
print("Groups crossing train/valid/test:", len(cross_split))

print("\nExamples of cross-split groups:")
for source_id, paths in list(cross_split.items())[:10]:
    print("\nSource:", source_id)
    for path in paths:
        print(" ", path.relative_to(base))
```

**Outputs:**

```
Total images: 3636
Unique filename-based source IDs: 3043
Repeated source-ID groups: 328
Groups crossing train/valid/test: 163

Examples of cross-split groups:

Source: 2-211-_jpg
  train/images/2-211-_jpg.rf.2ece648baaf8f7d7c28de034aa62643b.jpg
  train/images/2-211-_jpg.rf.b1047a4127ad174ec8c71f983a20f7f1.jpg
  valid/images/2-211-_jpg.rf.2e1d40a0ea1a5b0d493c9eea4484b457.jpg
  test/images/2-211-_jpg.rf.b25b6d5e4ec90cb8303ba210327a6289.jpg

Source: 1-9-_jpg
  train/images/1-9-_jpg.rf.1a61e0980d83da473c3742558aac56cd.jpg
  train/images/1-9-_jpg.rf.a49718a30dee108a6de4ac30ad92784a.jpg
  valid/images/1-9-_jpg.rf.807e60f66864c8b6eb2956eb237d9aec.jpg

Source: 2-295-_jpg
  train/images/2-295-_jpg.rf.11611dc3df6d645c27f20a717eda276b.jpg
  train/images/2-295-_jpg.rf.5c6ae1bdfd8a0ad12c01226239deff25.jpg
  valid/images/2-295-_jpg.rf.27a5d41bca0a81c81d36e89578ebb516.jpg

Source: 2-193-_jpg
  train/images/2-193-_jpg.rf.527cf5f32f2c9c5e92ea6a4b18e8e56e.jpg
  train/images/2-193-_jpg.rf.f43ebe708b71725a0e9fe62e44874396.jpg
  train/images/2-193-_jpg.rf.f065478423d0c4b9acc2dfd0a4c88f77.jpg
  valid/images/2-193-_jpg.rf.ab2621caaccc69084eecfe23c1ea47c0.jpg

Source: 1-87-_jpg
  train/images/1-87-_jpg.rf.e65cc6dae134200b59831de7f60c526e.jpg
  train/images/1-87-_jpg.rf.ffedad5390cacd774938e28309f0f44c.jpg
  valid/images/1-87-_jpg.rf.b61bed679f274eecfd0ba80c0b901dbe.jpg

Source: 2-118-_jpg
  train/images/2-118-_jpg.rf.d011d5df1b9395a70277f00f61e5ba2a.jpg
  train/images/2-118-_jpg.rf.91844bf57803502b98e797adccd4198a.jpg
  test/images/2-118-_jpg.rf.0b39d4b2b23bb33e07f9161e6a75499f.jpg

Source: 1-107-_jpg
  train/images/1-107-_jpg.rf.a3d8d90b96085c4cb18c51a3067b3f4f.jpg
  train/images/1-107-_jpg.rf.72fa9dcfdbd03878ee29de202ca60916.jpg
  valid/images/1-107-_jpg.rf.2bb394a489bc0ddbf79fd2a5e51933ea.jpg

Source: 2-236-_jpg
  train/images/2-236-_jpg.rf.8a40296f03f715867b3694e36b262be9.jpg
  valid/images/2-236-_jpg.rf.2478dda3cbbe8c93a7e0ccf7300ed947.jpg

Source: 2-26-_jpg
  train/images/2-26-_jpg.rf.da6a33440ee4cc43a5eaa31b7b8e1981.jpg
  train/images/2-26-_jpg.rf.3af41c44a5183be759e1b9f11c7ee93f.jpg
  test/images/2-26-_jpg.rf.8720dfdbdeddd4e42809b42c61e2ee2e.jpg

Source: 1-121-_jpg
  train/images/1-121-_jpg.rf.22fb42dd2db0ef2cd2bd16be2660bd98.jpg
  train/images/1-121-_jpg.rf.511a4fb324530c2701b107b7fdc5fb92.jpg
  valid/images/1-121-_jpg.rf.8cc1f3f1f2e6459ed4e2f18756eb5ccb.jpg

```

## Cell 27 [code]

```python
from pathlib import Path
from collections import defaultdict, Counter
import random
import shutil
import hashlib

base = Path("/content/solarguard_roboflow")
output = Path("/content/solarguard_v2_split")

class_map = {
    0: "Bird-Dropping",
    2: "Dusty",
    3: "Normal",
    4: "Surface-Damage"
}

records = defaultdict(list)
extensions = [".jpg", ".jpeg", ".png", ".webp"]

for old_split in ["train", "valid", "test"]:
    label_dir = base / old_split / "labels"
    image_dir = base / old_split / "images"

    for label_file in label_dir.glob("*.txt"):
        try:
            ids = {
                int(line.split()[0])
                for line in label_file.read_text().splitlines()
                if line.strip()
            }
        except (ValueError, IndexError):
            continue

        # Remove only the generic Defective label
        specific = ids - {1}

        # Accept exactly one supported specific class
        if len(specific) != 1:
            continue

        class_id = next(iter(specific))

        if class_id not in class_map:
            continue

        image_path = None

        for ext in extensions:
            candidate = image_dir / (label_file.stem + ext)
            if candidate.exists():
                image_path = candidate
                break

        if image_path is None:
            continue

        source_id = image_path.name.split(".rf.")[0].lower()

        records[source_id].append({
            "path": image_path,
            "label": class_map[class_id]
        })

# Exclude source groups with conflicting labels
clean_groups = defaultdict(list)
conflicting_groups = 0

for source_id, items in records.items():
    labels = {item["label"] for item in items}

    if len(labels) != 1:
        conflicting_groups += 1
        continue

    label = next(iter(labels))
    clean_groups[label].append((source_id, items))

print("Excluded conflicting source groups:", conflicting_groups)

# Fresh group-aware split, stratified by class
rng = random.Random(42)

if output.exists():
    shutil.rmtree(output)

summary = Counter()

for label, groups in clean_groups.items():
    rng.shuffle(groups)

    n = len(groups)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    assignments = {
        "train": groups[:train_end],
        "val": groups[train_end:val_end],
        "test": groups[val_end:]
    }

    for split_name, assigned_groups in assignments.items():
        target_dir = output / split_name / label
        target_dir.mkdir(parents=True, exist_ok=True)

        for source_id, items in assigned_groups:
            for item in items:
                path = item["path"]

                unique_name = hashlib.sha256(
                    str(path).encode()
                ).hexdigest()[:16] + path.suffix.lower()

                shutil.copy2(path, target_dir / unique_name)
                summary[(split_name, label)] += 1

print("\nCLEANED DATASET COUNTS:")

for split in ["train", "val", "test"]:
    print(f"\n{split.upper()}")
    total = 0

    for label in class_map.values():
        count = summary[(split, label)]
        print(f"{label}: {count}")
        total += count

    print("TOTAL:", total)

print("\nCleaned dataset created at:", output)
```

**Outputs:**

```
Excluded conflicting source groups: 2

CLEANED DATASET COUNTS:

TRAIN
Bird-Dropping: 70
Dusty: 713
Normal: 1201
Surface-Damage: 225
TOTAL: 2209

VAL
Bird-Dropping: 16
Dusty: 156
Normal: 259
Surface-Damage: 49
TOTAL: 480

TEST
Bird-Dropping: 14
Dusty: 150
Normal: 259
Surface-Damage: 68
TOTAL: 491

Cleaned dataset created at: /content/solarguard_v2_split

```

## Cell 28 [code]

```python
from pathlib import Path
from PIL import Image, ImageOps
from collections import defaultdict
import numpy as np
import hashlib

original = Path("/content/solar_dataset/Faulty_solar_panel")
new = Path("/content/solarguard_v2_split")

extensions = {".jpg", ".jpeg", ".png", ".webp"}

original_files = [
    p for p in original.rglob("*")
    if p.is_file() and p.suffix.lower() in extensions
]

new_files = [
    p for p in new.rglob("*")
    if p.is_file() and p.suffix.lower() in extensions
]

print("Original images:", len(original_files))
print("New dataset images:", len(new_files))

def image_hash(path):
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("L")
        img = img.resize((9, 8))

        pixels = np.asarray(img, dtype=np.int16)
        differences = pixels[:, 1:] > pixels[:, :-1]

        return tuple(differences.flatten().tolist())

def hash_distance(a, b):
    return sum(x != y for x, y in zip(a, b))

original_hashes = []
new_hashes = []

for p in original_files:
    try:
        original_hashes.append((p, image_hash(p)))
    except Exception:
        pass

for p in new_files:
    try:
        new_hashes.append((p, image_hash(p)))
    except Exception:
        pass

matches = []

for old_path, old_hash in original_hashes:
    for new_path, new_hash in new_hashes:
        distance = hash_distance(old_hash, new_hash)

        if distance <= 5:
            matches.append((old_path, new_path, distance))

print("\nPotential near-duplicate pairs:", len(matches))

for old_path, new_path, distance in matches[:15]:
    print("\nOriginal:", old_path.name)
    print("New:", new_path.relative_to(new))
    print("Hash distance:", distance)
```

**Outputs:**

```
Original images: 885
New dataset images: 3180

Potential near-duplicate pairs: 396

Original: Bird (121).jpg
New: train/Bird-Dropping/2dfcb85c2c5f76fd.jpg
Hash distance: 1

Original: Bird (39).jpg
New: train/Dusty/0dd06d6f29565dbb.jpg
Hash distance: 0

Original: Bird (39).jpg
New: train/Dusty/92425cce3d5c5627.jpg
Hash distance: 0

Original: Bird (39).jpg
New: train/Dusty/b39af9c5d6b32e9c.jpg
Hash distance: 0

Original: Bird (39).jpg
New: val/Dusty/f4fe5c518e4724c3.jpg
Hash distance: 0

Original: Bird (39).jpg
New: val/Dusty/b896e5c3db8e0fed.jpg
Hash distance: 0

Original: Bird (39).jpg
New: val/Dusty/0a37107527f25fde.jpg
Hash distance: 0

Original: Bird (69).JPG
New: train/Dusty/734a11d8ba177fa4.jpg
Hash distance: 2

Original: Bird (169).jpg
New: train/Bird-Dropping/246dc26c99e6711f.jpg
Hash distance: 2

Original: Bird (148).jpg
New: train/Bird-Dropping/745d8dc5d94cfd72.jpg
Hash distance: 0

Original: Bird (71).jpg
New: train/Bird-Dropping/ddb7cb638497e64a.jpg
Hash distance: 1

Original: Bird (71).jpg
New: val/Bird-Dropping/e6c7966dfc50c73b.jpg
Hash distance: 0

Original: Bird (64).jpg
New: train/Dusty/0dd06d6f29565dbb.jpg
Hash distance: 0

Original: Bird (64).jpg
New: train/Dusty/92425cce3d5c5627.jpg
Hash distance: 0

Original: Bird (64).jpg
New: train/Dusty/b39af9c5d6b32e9c.jpg
Hash distance: 0

```

## Cell 29 [code]

```python
from pathlib import Path
from collections import defaultdict, Counter
from PIL import Image, ImageOps
import numpy as np

base = Path("/content/solarguard_v2_split")
extensions = {".jpg", ".jpeg", ".png", ".webp"}

files = [
    p for p in base.rglob("*")
    if p.is_file() and p.suffix.lower() in extensions
]

def dhash(path):
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("L")
        img = img.resize((9, 8))
        pixels = np.asarray(img, dtype=np.int16)
        return tuple((pixels[:, 1:] > pixels[:, :-1]).flatten())

hashes = []

for p in files:
    try:
        hashes.append((p, dhash(p)))
    except Exception as e:
        print("Unreadable:", p, e)

# First check identical perceptual hashes
groups = defaultdict(list)

for path, h in hashes:
    groups[h].append(path)

duplicate_groups = [
    paths for paths in groups.values()
    if len(paths) > 1
]

cross_split_groups = [
    paths for paths in duplicate_groups
    if len({p.relative_to(base).parts[0] for p in paths}) > 1
]

conflicting_label_groups = [
    paths for paths in duplicate_groups
    if len({p.relative_to(base).parts[1] for p in paths}) > 1
]

print("Total images:", len(files))
print("Identical perceptual-hash groups:", len(duplicate_groups))
print("Groups crossing splits:", len(cross_split_groups))
print("Groups with conflicting labels:", len(conflicting_label_groups))

print("\nExamples of cross-split groups:")
for group in cross_split_groups[:10]:
    print("---")
    for p in group:
        print(p.relative_to(base))
```

**Outputs:**

```
Total images: 3180
Identical perceptual-hash groups: 211
Groups crossing splits: 28
Groups with conflicting labels: 0

Examples of cross-split groups:
---
test/Bird-Dropping/9451cceb65d3a848.jpg
test/Bird-Dropping/673fe77408d783e5.jpg
train/Bird-Dropping/85f42259a29f2574.jpg
---
test/Bird-Dropping/331ddc46a4e58583.jpg
train/Bird-Dropping/462d029aacecf17a.jpg
---
test/Dusty/17a26363ab12d196.jpg
train/Dusty/8f50e967c3021b0a.jpg
---
test/Dusty/07401de133cd2b0b.jpg
train/Dusty/243a8d23df828c5e.jpg
train/Dusty/fa03fa95587f67c9.jpg
train/Dusty/9f60cc3dbc2ba99a.jpg
train/Dusty/8e3cebdde6a4a340.jpg
train/Dusty/aab629937f1fcbcd.jpg
train/Dusty/21c030bd3308e9d1.jpg
train/Dusty/b4aa213b7f94a506.jpg
train/Dusty/3097459eee0541f8.jpg
train/Dusty/874a818cccf3c8eb.jpg
---
test/Dusty/e8aa08238a17dffd.jpg
train/Dusty/6f60afa46165945f.jpg
train/Dusty/f4f041897999dd73.jpg
---
test/Dusty/7fe88f1320c41ebb.jpg
test/Dusty/43dbf0806f5aaa60.jpg
train/Dusty/cb653848b46e8aef.jpg
train/Dusty/f1b428ebee9c2d06.jpg
---
test/Dusty/0cc6f59ee6ed7975.jpg
train/Dusty/32d98bea94f18c93.jpg
---
test/Surface-Damage/0d007931160734b4.jpg
test/Surface-Damage/4bc8d5cc741d5f80.jpg
train/Surface-Damage/3777a28c871af485.jpg
train/Surface-Damage/14be40f34144b296.jpg
---
test/Surface-Damage/bea0e08a56dc79ce.jpg
val/Surface-Damage/6a176335a0beabb2.jpg
---
test/Surface-Damage/b94bc4f682b5334f.jpg
train/Surface-Damage/0697855285c61ea8.jpg

```

## Cell 30 [code]

```python
from pathlib import Path
from collections import defaultdict, Counter
from PIL import Image, ImageOps
import numpy as np
import shutil

source = Path("/content/solarguard_v2_split")
destination = Path("/content/solarguard_v2_clean")

extensions = {".jpg", ".jpeg", ".png", ".webp"}

def dhash(path):
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("L")
        img = img.resize((9, 8))
        pixels = np.asarray(img, dtype=np.int16)
        return tuple((pixels[:, 1:] > pixels[:, :-1]).flatten())

groups = defaultdict(list)

for path in source.rglob("*"):
    if path.is_file() and path.suffix.lower() in extensions:
        try:
            groups[dhash(path)].append(path)
        except Exception as e:
            print("Skipped unreadable image:", path, e)

# Prefer training copies, then validation, then test.
# This preserves more training data, but evaluation sets may shrink.
priority = {"train": 0, "val": 1, "test": 2}

if destination.exists():
    shutil.rmtree(destination)

counts = Counter()
conflicts = 0

for image_group in groups.values():
    labels = {
        p.relative_to(source).parts[1]
        for p in image_group
    }

    # Don't silently choose a label if identical hashes
    # have conflicting classes.
    if len(labels) > 1:
        conflicts += 1
        continue

    selected = min(
        image_group,
        key=lambda p: (
            priority[p.relative_to(source).parts[0]],
            str(p)
        )
    )

    relative = selected.relative_to(source)
    target = destination / relative

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(selected, target)

    counts[(relative.parts[0], relative.parts[1])] += 1

print("Conflicting groups excluded:", conflicts)
print("Unique retained images:", sum(counts.values()))

for split in ["train", "val", "test"]:
    print(f"\n{split.upper()}")
    total = 0

    for label in [
        "Bird-Dropping",
        "Dusty",
        "Normal",
        "Surface-Damage"
    ]:
        count = counts[(split, label)]
        print(f"{label}: {count}")
        total += count

    print("TOTAL:", total)
```

**Outputs:**

```
Conflicting groups excluded: 0
Unique retained images: 2809

TRAIN
Bird-Dropping: 48
Dusty: 607
Normal: 1173
Surface-Damage: 146
TOTAL: 1974

VAL
Bird-Dropping: 10
Dusty: 129
Normal: 248
Surface-Damage: 28
TOTAL: 415

TEST
Bird-Dropping: 10
Dusty: 129
Normal: 249
Surface-Damage: 32
TOTAL: 420

```

## Cell 31 [code]

```python
from pathlib import Path
from PIL import Image, ImageOps
import numpy as np
from collections import Counter

original = Path("/content/solar_dataset/Faulty_solar_panel")
cleaned = Path("/content/solarguard_v2_clean")

extensions = {".jpg", ".jpeg", ".png", ".webp"}

def dhash(path):
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("L")
        img = img.resize((9, 8))
        arr = np.asarray(img, dtype=np.int16)
        return (arr[:, 1:] > arr[:, :-1]).flatten()

def distance(a, b):
    return np.count_nonzero(a != b)

clean_hashes = []

for path in cleaned.rglob("*"):
    if path.is_file() and path.suffix.lower() in extensions:
        try:
            clean_hashes.append(dhash(path))
        except Exception:
            pass

print("Cleaned reference images:", len(clean_hashes))

folders = {
    "Bird-Dropping": [
        original / "Bird-drop",
        original / "Bird-drop" / "New"
    ],
    "Surface-Damage": [
        original / "Physical-Damage"
    ]
}

for label, paths in folders.items():
    candidates = {}

    for folder in paths:
        if folder.exists():
            for p in folder.rglob("*"):
                if p.is_file() and p.suffix.lower() in extensions:
                    candidates[str(p)] = p

    counts = Counter()
    examples = []

    for path in candidates.values():
        try:
            h = dhash(path)

            nearest = min(
                distance(h, existing)
                for existing in clean_hashes
            )

            if nearest <= 5:
                counts["potential_overlap"] += 1
            else:
                counts["potentially_new"] += 1
                examples.append(path.name)

        except Exception:
            counts["unreadable"] += 1

    print(f"\n{label}")
    print("Original candidates:", len(candidates))
    print("Potential overlaps:", counts["potential_overlap"])
    print("Potentially new:", counts["potentially_new"])
    print("Example new filenames:", examples[:10])
```

**Outputs:**

```
Cleaned reference images: 2809

Bird-Dropping
Original candidates: 207
Potential overlaps: 81
Potentially new: 126
Example new filenames: ['Bird (61).jpg', 'Bird (87).jpg', 'Bird (99).jpg', 'Bird (38).jpg', 'Bird (150).jpg', 'Bird (197).jpg', 'Bird (27).JPG', 'Bird (188).jpg', 'Bird (41).jpg', 'Bird (119).jpg']

Surface-Damage
Original candidates: 69
Potential overlaps: 17
Potentially new: 52
Example new filenames: ['Physical (44).jpg', 'Physical (45).jpg', 'Physical (6).jpg', 'Physical (4).jpg', 'Physical (30).jpg', 'Physical (51).jpg', 'Physical (17).jpg', 'Physical (11).jpg', 'Physical (50).jpg', 'Physical (55).jpg']

```

## Cell 32 [code]

```python
from pathlib import Path
from PIL import Image, ImageOps
from collections import Counter
import numpy as np
import shutil
import hashlib

original = Path("/content/solar_dataset/Faulty_solar_panel")
cleaned = Path("/content/solarguard_v2_clean")
extra = Path("/content/solarguard_v2_extra_train")

extensions = {".jpg", ".jpeg", ".png", ".webp"}

def dhash(path):
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("L")
        img = img.resize((9, 8))
        arr = np.asarray(img, dtype=np.int16)
        return (arr[:, 1:] > arr[:, :-1]).flatten()

def distance(a, b):
    return int(np.count_nonzero(a != b))

reference_hashes = []

for path in cleaned.rglob("*"):
    if path.is_file() and path.suffix.lower() in extensions:
        try:
            reference_hashes.append(dhash(path))
        except Exception:
            pass

folders = {
    "Bird-Dropping": original / "Bird-drop",
    "Surface-Damage": original / "Physical-Damage"
}

if extra.exists():
    shutil.rmtree(extra)

counts = Counter()

for label, folder in folders.items():
    target = extra / label
    target.mkdir(parents=True, exist_ok=True)

    accepted_hashes = []

    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue

        try:
            h = dhash(path)

            # Check against the entire cleaned dataset,
            # including validation and test images.
            overlaps_existing = any(
                distance(h, ref) <= 5
                for ref in reference_hashes
            )

            # Also prevent near-duplicates among additions.
            overlaps_extra = any(
                distance(h, ref) <= 5
                for ref in accepted_hashes
            )

            if overlaps_existing or overlaps_extra:
                counts[(label, "excluded")] += 1
                continue

            unique_name = (
                hashlib.sha256(str(path).encode()).hexdigest()[:16]
                + path.suffix.lower()
            )

            shutil.copy2(path, target / unique_name)
            accepted_hashes.append(h)
            counts[(label, "added")] += 1

        except Exception as e:
            print("Skipped:", path.name, e)

for label in folders:
    print(f"\n{label}")
    print("Additional candidates:", counts[(label, "added")])
    print("Excluded:", counts[(label, "excluded")])

print("\nSaved to:", extra)
```

**Outputs:**

```

Bird-Dropping
Additional candidates: 81
Excluded: 126

Surface-Damage
Additional candidates: 40
Excluded: 29

Saved to: /content/solarguard_v2_extra_train

```

## Cell 33 [code]

```python
from pathlib import Path
from collections import Counter
import shutil

cleaned = Path("/content/solarguard_v2_clean")
extra = Path("/content/solarguard_v2_extra_train")
final = Path("/content/solarguard_v2_final")

classes = [
    "Bird-Dropping",
    "Dusty",
    "Normal",
    "Surface-Damage"
]

# Rebuild only the output folder; original datasets stay untouched.
if final.exists():
    shutil.rmtree(final)

shutil.copytree(cleaned, final)

added = Counter()

for label in ["Bird-Dropping", "Surface-Damage"]:
    source_folder = extra / label
    target_folder = final / "train" / label

    for image_path in source_folder.iterdir():
        if not image_path.is_file():
            continue

        target_path = target_folder / ("extra_" + image_path.name)

        shutil.copy2(image_path, target_path)
        added[label] += 1

print("Additional training images:", sum(added.values()))

for split in ["train", "val", "test"]:
    print(f"\n{split.upper()}")

    total = 0

    for label in classes:
        folder = final / split / label

        count = sum(
            1 for p in folder.iterdir()
            if p.is_file()
        )

        print(f"{label}: {count}")
        total += count

    print("TOTAL:", total)

print("\nFinal dataset location:", final)
```

**Outputs:**

```
Additional training images: 121

TRAIN
Bird-Dropping: 129
Dusty: 607
Normal: 1173
Surface-Damage: 186
TOTAL: 2095

VAL
Bird-Dropping: 10
Dusty: 129
Normal: 248
Surface-Damage: 28
TOTAL: 415

TEST
Bird-Dropping: 10
Dusty: 129
Normal: 249
Surface-Damage: 32
TOTAL: 420

Final dataset location: /content/solarguard_v2_final

```

## Cell 34 [code]

```python
import tensorflow as tf
import numpy as np
from pathlib import Path
from collections import Counter

DATASET = Path("/content/solarguard_v2_final")

CLASS_NAMES = [
    "Bird-Dropping",
    "Dusty",
    "Normal",
    "Surface-Damage"
]

IMG_SIZE = (224, 224)
BATCH_SIZE = 32
SEED = 42

print("TensorFlow version:", tf.__version__)
print("GPU available:", tf.config.list_physical_devices("GPU"))

train_ds = tf.keras.utils.image_dataset_from_directory(
    DATASET / "train",
    labels="inferred",
    label_mode="int",
    class_names=CLASS_NAMES,
    image_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    shuffle=True,
    seed=SEED
)

val_ds = tf.keras.utils.image_dataset_from_directory(
    DATASET / "val",
    labels="inferred",
    label_mode="int",
    class_names=CLASS_NAMES,
    image_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    shuffle=False
)

test_ds = tf.keras.utils.image_dataset_from_directory(
    DATASET / "test",
    labels="inferred",
    label_mode="int",
    class_names=CLASS_NAMES,
    image_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    shuffle=False
)

# Calculate class weights using training data only
counts = np.array([
    len(list((DATASET / "train" / name).glob("*")))
    for name in CLASS_NAMES
], dtype=np.float32)

total = counts.sum()

class_weights = {
    i: float(total / (len(CLASS_NAMES) * count))
    for i, count in enumerate(counts)
}

print("\nClass names:", CLASS_NAMES)
print("Training counts:", counts.astype(int).tolist())
print("Class weights:", class_weights)

AUTOTUNE = tf.data.AUTOTUNE

train_ds = train_ds.prefetch(AUTOTUNE)
val_ds = val_ds.prefetch(AUTOTUNE)
test_ds = test_ds.prefetch(AUTOTUNE)

print("\nDataset loading complete.")
```

**Outputs:**

```
TensorFlow version: 2.21.0
GPU available: [PhysicalDevice(name='/physical_device:GPU:0', device_type='GPU')]
Found 2095 files belonging to 4 classes.
Found 415 files belonging to 4 classes.
Found 420 files belonging to 4 classes.

Class names: ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage']
Training counts: [129, 607, 1173, 186]
Class weights: {0: 4.060077667236328, 1: 0.8628500699996948, 2: 0.446504682302475, 3: 2.8158602714538574}

Dataset loading complete.

```

## Cell 35 [code]

```python
import tensorflow as tf
from tensorflow.keras import layers, Model
from tensorflow.keras.applications import MobileNetV2

tf.keras.utils.set_random_seed(42)

# Training-only augmentation
augmentation = tf.keras.Sequential([
    layers.RandomFlip("horizontal"),
    layers.RandomRotation(0.08),
    layers.RandomZoom(0.10),
    layers.RandomContrast(0.10),
], name="training_augmentation")

# Pretrained feature extractor
backbone = MobileNetV2(
    input_shape=(224, 224, 3),
    include_top=False,
    weights="imagenet"
)

# Freeze pretrained layers initially
backbone.trainable = False

inputs = layers.Input(shape=(224, 224, 3), name="image_input")

# Augmentation is automatically disabled during inference
x = augmentation(inputs)

# Raw RGB pixels (0–255) -> MobileNetV2 input range (-1 to 1)
x = layers.Rescaling(
    scale=1.0 / 127.5,
    offset=-1
)(x)

# Keep backbone BatchNorm layers in inference mode
x = backbone(x, training=False)

x = layers.GlobalAveragePooling2D()(x)
x = layers.Dropout(0.35)(x)

outputs = layers.Dense(
    4,
    activation="softmax",
    name="predictions"
)(x)

model_v2 = Model(inputs, outputs, name="SolarGuard_V2")

model_v2.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.0003),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"]
)

callbacks = [
    tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=4,
        restore_best_weights=True
    ),
    tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=2,
        min_lr=1e-6
    )
]

print("Starting SolarGuard Version 2 training...")

history_v2 = model_v2.fit(
    train_ds,
    validation_data=val_ds,
    epochs=15,
    class_weight=class_weights,
    callbacks=callbacks
)

print("\nTraining completed.")
```

**Outputs:**

```
Downloading data from https://storage.googleapis.com/tensorflow/keras-applications/mobilenet_v2/mobilenet_v2_weights_tf_dim_ordering_tf_kernels_1.0_224_no_top.h5
[1m9406464/9406464[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m0s[0m 0us/step
Starting SolarGuard Version 2 training...
Epoch 1/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m18s[0m 120ms/step - accuracy: 0.4072 - loss: 1.6345 - val_accuracy: 0.5253 - val_loss: 1.0773 - learning_rate: 3.0000e-04
Epoch 2/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 97ms/step - accuracy: 0.6272 - loss: 1.1076 - val_accuracy: 0.6940 - val_loss: 0.8381 - learning_rate: 3.0000e-04
Epoch 3/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m10s[0m 97ms/step - accuracy: 0.6893 - loss: 0.9775 - val_accuracy: 0.7422 - val_loss: 0.6911 - learning_rate: 3.0000e-04
Epoch 4/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m6s[0m 95ms/step - accuracy: 0.7389 - loss: 0.8302 - val_accuracy: 0.7904 - val_loss: 0.6038 - learning_rate: 3.0000e-04
Epoch 5/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 98ms/step - accuracy: 0.7499 - loss: 0.7824 - val_accuracy: 0.7880 - val_loss: 0.5856 - learning_rate: 3.0000e-04
Epoch 6/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m11s[0m 101ms/step - accuracy: 0.7833 - loss: 0.7122 - val_accuracy: 0.7904 - val_loss: 0.5773 - learning_rate: 3.0000e-04
Epoch 7/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m10s[0m 101ms/step - accuracy: 0.7914 - loss: 0.6978 - val_accuracy: 0.8337 - val_loss: 0.5009 - learning_rate: 3.0000e-04
Epoch 8/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 101ms/step - accuracy: 0.8014 - loss: 0.6454 - val_accuracy: 0.8313 - val_loss: 0.4777 - learning_rate: 3.0000e-04
Epoch 9/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 99ms/step - accuracy: 0.8291 - loss: 0.5838 - val_accuracy: 0.8241 - val_loss: 0.4920 - learning_rate: 3.0000e-04
Epoch 10/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 101ms/step - accuracy: 0.8100 - loss: 0.6163 - val_accuracy: 0.8313 - val_loss: 0.4663 - learning_rate: 3.0000e-04
Epoch 11/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m6s[0m 97ms/step - accuracy: 0.8263 - loss: 0.5927 - val_accuracy: 0.8313 - val_loss: 0.4479 - learning_rate: 3.0000e-04
Epoch 12/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m11s[0m 100ms/step - accuracy: 0.8334 - loss: 0.5646 - val_accuracy: 0.8458 - val_loss: 0.4266 - learning_rate: 3.0000e-04
Epoch 13/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m7s[0m 99ms/step - accuracy: 0.8430 - loss: 0.5381 - val_accuracy: 0.8386 - val_loss: 0.4309 - learning_rate: 3.0000e-04
Epoch 14/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m10s[0m 94ms/step - accuracy: 0.8434 - loss: 0.5418 - val_accuracy: 0.8530 - val_loss: 0.4015 - learning_rate: 3.0000e-04
Epoch 15/15
[1m66/66[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m10s[0m 93ms/step - accuracy: 0.8468 - loss: 0.4856 - val_accuracy: 0.8458 - val_loss: 0.4169 - learning_rate: 3.0000e-04

Training completed.

```

## Cell 36 [code]

```python
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay
)

# Evaluate on held-out test images
test_loss, test_accuracy = model_v2.evaluate(
    test_ds,
    verbose=1
)

# Get model predictions
probabilities = model_v2.predict(test_ds, verbose=1)
y_pred = np.argmax(probabilities, axis=1)

# Get true labels (test_ds was created with shuffle=False)
y_true = np.concatenate([
    labels.numpy()
    for images, labels in test_ds
])

print("\n" + "=" * 45)
print("SOLARGUARD VERSION 2 — TEST RESULTS")
print("=" * 45)

print(f"Test accuracy: {test_accuracy * 100:.2f}%")
print(f"Test loss: {test_loss:.4f}")

print("\nClassification report:")
print(
    classification_report(
        y_true,
        y_pred,
        labels=list(range(4)),
        target_names=CLASS_NAMES,
        digits=3,
        zero_division=0
    )
)

cm = confusion_matrix(
    y_true,
    y_pred,
    labels=list(range(4))
)

fig, ax = plt.subplots(figsize=(8, 7))

disp = ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=CLASS_NAMES
)

disp.plot(
    ax=ax,
    cmap="Blues",
    values_format="d",
    colorbar=False
)

plt.title("SolarGuard V2 — Test Confusion Matrix")
plt.xticks(rotation=25, ha="right")
plt.tight_layout()
plt.show()
```

**Outputs:**

```
[1m14/14[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m2s[0m 117ms/step - accuracy: 0.8524 - loss: 0.4391
[1m14/14[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m4s[0m 137ms/step

=============================================
SOLARGUARD VERSION 2 — TEST RESULTS
=============================================
Test accuracy: 85.24%
Test loss: 0.4391

Classification report:
                precision    recall  f1-score   support

 Bird-Dropping      0.192     0.500     0.278        10
         Dusty      0.880     0.798     0.837       129
        Normal      0.962     0.904     0.932       249
Surface-Damage      0.581     0.781     0.667        32

      accuracy                          0.852       420
     macro avg      0.654     0.746     0.678       420
  weighted avg      0.889     0.852     0.867       420

<Figure size 800x700 with 1 Axes>
```

## Cell 37 [code]

```python
import json
from pathlib import Path
from google.colab import drive

drive.mount("/content/drive")

save_dir = Path("/content/drive/MyDrive/SolarGuard_Model")
save_dir.mkdir(parents=True, exist_ok=True)

model_path = save_dir / "solarguard_model_v2.keras"
metadata_path = save_dir / "model_metadata_v2.json"

# Save Version 2 without overwriting Version 1
model_v2.save(str(model_path))

metadata = {
    "model_version": "2.0",
    "architecture": "MobileNetV2",
    "class_names": [
        "Bird-Dropping",
        "Dusty",
        "Normal",
        "Surface-Damage"
    ],
    "image_size": [224, 224],
    "input_color_mode": "RGB",
    "input_pixel_range": [0, 255],
    "preprocessing": "Built into model: Rescaling(1/127.5, offset=-1)",
    "test_accuracy": 0.8524,
    "test_images": 420,
    "note": "Preliminary experimental evaluation; not validated for real-world safety-critical inspection."
}

with open(metadata_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=4)

print("Model saved:", model_path)
print("Metadata saved:", metadata_path)
print("Model file size:", round(model_path.stat().st_size / (1024**2), 2), "MB")
```

**Outputs:**

```
Drive already mounted at /content/drive; to attempt to forcibly remount, call drive.mount("/content/drive", force_remount=True).
Model saved: /content/drive/MyDrive/SolarGuard_Model/solarguard_model_v2.keras
Metadata saved: /content/drive/MyDrive/SolarGuard_Model/model_metadata_v2.json
Model file size: 9.25 MB

```

## Cell 38 [markdown]

Adding both datasets

## Cell 39 [code]

```python
from pathlib import Path

kaggle = Path("/content/solar_dataset/Faulty_solar_panel")

print("KAGGLE DATASET CATEGORIES\n")

for folder in sorted(kaggle.iterdir()):
    if folder.is_dir():
        images = [
            p for p in folder.rglob("*")
            if p.suffix.lower() in
            {".jpg", ".jpeg", ".png", ".webp"}
        ]

        print(f"{folder.name}: {len(images)} images")

print("\nCURRENT MODEL CATEGORIES:")
print("1. Bird-Dropping")
print("2. Dusty")
print("3. Normal")
print("4. Surface-Damage")
```

**Outputs:**

```
KAGGLE DATASET CATEGORIES

Bird-drop: 207 images
Clean: 193 images
Dusty: 190 images
Electrical-damage: 103 images
Physical-Damage: 69 images
Snow-Covered: 123 images

CURRENT MODEL CATEGORIES:
1. Bird-Dropping
2. Dusty
3. Normal
4. Surface-Damage

```

## Cell 40 [code]

```python
from pathlib import Path
from PIL import Image, ImageOps
from collections import defaultdict
import numpy as np

root = Path("/content/solar_dataset/Faulty_solar_panel")

folders = {
    "Bird-Dropping": "Bird-drop",
    "Dusty": "Dusty",
    "Normal": "Clean",
    "Surface-Damage": "Physical-Damage"
}

def dhash(path):
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("L")
        img = img.resize((9, 8))
        pixels = np.asarray(img, dtype=np.int16)
        return tuple((pixels[:, 1:] > pixels[:, :-1]).flatten())

groups = defaultdict(list)

for label, folder_name in folders.items():
    for path in (root / folder_name).rglob("*"):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue

        try:
            groups[dhash(path)].append((label, path))
        except Exception as e:
            print("Skipped:", path, e)

duplicates = [g for g in groups.values() if len(g) > 1]
conflicts = [
    g for g in duplicates
    if len({label for label, path in g}) > 1
]

print("Total relevant Kaggle images:",
      sum(len(g) for g in groups.values()))
print("Unique perceptual hashes:", len(groups))
print("Duplicate-hash groups:", len(duplicates))
print("Conflicting-label groups:", len(conflicts))

print("\nExamples of conflicting labels:")
for group in conflicts[:10]:
    print("---")
    for label, path in group:
        print(label, path.name)
```

**Outputs:**

```
Total relevant Kaggle images: 659
Unique perceptual hashes: 559
Duplicate-hash groups: 66
Conflicting-label groups: 3

Examples of conflicting labels:
---
Bird-Dropping Bird (193).jpg
Dusty Dust (187).jpg
---
Bird-Dropping Bird (176).jpg
Bird-Dropping Bird (46).jpg
Bird-Dropping Bird (22).jpg
Bird-Dropping Bird (140).jpg
Bird-Dropping Bird (184).jpg
Bird-Dropping Bird (57).jpg
Surface-Damage Physical (51).jpg
---
Bird-Dropping Bird (3).jpeg
Surface-Damage Physical (44).jpg

```

## Cell 41 [code]

```python
import matplotlib.pyplot as plt
from PIL import Image

print("Conflicting groups:", len(conflicts))

for group_number, group in enumerate(conflicts, start=1):
    print(f"\nGROUP {group_number}")

    n = len(group)

    fig, axes = plt.subplots(
        1, n,
        figsize=(min(4 * n, 24), 4)
    )

    if n == 1:
        axes = [axes]

    for ax, (label, path) in zip(axes, group):
        with Image.open(path) as img:
            ax.imshow(img.convert("RGB"))

        ax.set_title(
            f"{label}\n{path.name}",
            fontsize=9
        )
        ax.axis("off")

    plt.tight_layout()
    plt.show()
```

**Outputs:**

```
Conflicting groups: 3

GROUP 1
<Figure size 800x400 with 2 Axes>
GROUP 2
<Figure size 2400x400 with 7 Axes>
GROUP 3
<Figure size 800x400 with 2 Axes>
```

## Cell 42 [code]

```python
from pathlib import Path
from PIL import Image, ImageOps
from collections import defaultdict, Counter
import numpy as np

KAGGLE = Path("/content/solar_dataset/Faulty_solar_panel")

folder_map = {
    "Bird-Dropping": "Bird-drop",
    "Dusty": "Dusty",
    "Normal": "Clean",
    "Surface-Damage": "Physical-Damage"
}

def dhash(path):
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("L").resize((9, 8))
        a = np.asarray(img, dtype=np.int16)
        return tuple((a[:, 1:] > a[:, :-1]).flatten())

hash_groups = defaultdict(list)

for label, folder in folder_map.items():
    for p in (KAGGLE / folder).rglob("*"):
        if p.is_file() and p.suffix.lower() in {
            ".jpg", ".jpeg", ".png", ".webp"
        }:
            try:
                hash_groups[dhash(p)].append((label, p))
            except Exception:
                pass

clean_kaggle = []
excluded_conflict_images = 0

for h, items in hash_groups.items():

    labels = {label for label, _ in items}

    # Ambiguous duplicate group -> exclude whole group
    if len(labels) > 1:
        excluded_conflict_images += len(items)
        continue

    # Same class duplicates -> retain ONE representative
    clean_kaggle.append(items[0])

counts = Counter(label for label, _ in clean_kaggle)

print("CLEAN KAGGLE POOL")
print("-----------------")

for label in folder_map:
    print(f"{label}: {counts[label]}")

print("\nTotal unique retained:", len(clean_kaggle))
print(
    "Images excluded because their duplicate group "
    "had conflicting labels:",
    excluded_conflict_images
)
```

**Outputs:**

```
CLEAN KAGGLE POOL
-----------------
Bird-Dropping: 138
Dusty: 181
Normal: 183
Surface-Damage: 54

Total unique retained: 556
Images excluded because their duplicate group had conflicting labels: 11

```

## Cell 43 [code]

```python
from pathlib import Path
from collections import defaultdict, Counter
from PIL import Image, ImageOps
import numpy as np
import hashlib
import shutil
import random

KAGGLE = Path("/content/solar_dataset/Faulty_solar_panel")
ROBOFLOW = Path("/content/solarguard_roboflow")
OUTPUT = Path("/content/solarguard_v3_combined")

FOLDERS = {
    "Bird-Dropping": "Bird-drop",
    "Dusty": "Dusty",
    "Normal": "Clean",
    "Surface-Damage": "Physical-Damage"
}

CLASS_MAP = {
    0: "Bird-Dropping",
    2: "Dusty",
    3: "Normal",
    4: "Surface-Damage"
}

EXTS = {".jpg", ".jpeg", ".png", ".webp"}

def dhash(path):
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("L")
        img = img.resize((9, 8))
        arr = np.asarray(img, dtype=np.int16)
        return tuple((arr[:, 1:] > arr[:, :-1]).flatten())

# Gather images and their source identities
records = []

for label, folder in FOLDERS.items():
    for path in (KAGGLE / folder).rglob("*"):
        if path.is_file() and path.suffix.lower() in EXTS:
            records.append({
                "path": path,
                "label": label,
                "source": "kaggle:" + str(path.relative_to(KAGGLE))
            })

for split in ["train", "valid", "test"]:
    image_dir = ROBOFLOW / split / "images"
    label_dir = ROBOFLOW / split / "labels"

    for path in image_dir.iterdir():
        if path.suffix.lower() not in EXTS:
            continue

        label_path = label_dir / (path.stem + ".txt")
        if not label_path.exists():
            continue

        try:
            ids = {
                int(line.split()[0])
                for line in label_path.read_text().splitlines()
                if line.strip()
            }
        except (ValueError, IndexError):
            continue

        specific = ids - {1}

        if len(specific) != 1:
            continue

        class_id = next(iter(specific))

        if class_id not in CLASS_MAP:
            continue

        records.append({
            "path": path,
            "label": CLASS_MAP[class_id],
            "source": "roboflow:" + path.name.split(".rf.")[0].lower()
        })

print("Candidate files:", len(records))

# Union-find: group matching source IDs and identical perceptual hashes
parent = list(range(len(records)))

def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x

def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[rb] = ra

source_seen = {}
hash_seen = {}

valid_indices = []

for i, record in enumerate(records):
    try:
        h = dhash(record["path"])
    except Exception:
        continue

    valid_indices.append(i)

    source = record["source"]

    if source in source_seen:
        union(i, source_seen[source])
    else:
        source_seen[source] = i

    if h in hash_seen:
        union(i, hash_seen[h])
    else:
        hash_seen[h] = i

groups = defaultdict(list)

for i in valid_indices:
    groups[find(i)].append(records[i])

# Remove conflicting groups, retain one image per group
clean = defaultdict(list)
conflicts = 0
excluded_files = 0

for items in groups.values():
    labels = {item["label"] for item in items}

    if len(labels) != 1:
        conflicts += 1
        excluded_files += len(items)
        continue

    label = next(iter(labels))
    representative = items[0]
    clean[label].append(representative)

print("Conflicting groups excluded:", conflicts)
print("Files excluded due to conflicts:", excluded_files)

# Fresh stratified split at group level
rng = random.Random(42)

if OUTPUT.exists():
    shutil.rmtree(OUTPUT)

counts = Counter()

for label, items in clean.items():
    rng.shuffle(items)

    n = len(items)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    for split_name, selected in {
        "train": items[:train_end],
        "val": items[train_end:val_end],
        "test": items[val_end:]
    }.items():

        target_dir = OUTPUT / split_name / label
        target_dir.mkdir(parents=True, exist_ok=True)

        for item in selected:
            path = item["path"]

            filename = (
                hashlib.sha256(str(path).encode()).hexdigest()[:16]
                + path.suffix.lower()
            )

            shutil.copy2(path, target_dir / filename)
            counts[(split_name, label)] += 1

print("\nSOLARGUARD V3 DATASET")

for split in ["train", "val", "test"]:
    print(f"\n{split.upper()}")
    total = 0

    for label in FOLDERS:
        count = counts[(split, label)]
        print(f"{label}: {count}")
        total += count

    print("TOTAL:", total)

print("\nSaved to:", OUTPUT)
```

**Outputs:**

```
Candidate files: 3844
Conflicting groups excluded: 17
Files excluded due to conflicts: 73

SOLARGUARD V3 DATASET

TRAIN
Bird-Dropping: 116
Dusty: 690
Normal: 1294
Surface-Damage: 151
TOTAL: 2251

VAL
Bird-Dropping: 25
Dusty: 148
Normal: 277
Surface-Damage: 32
TOTAL: 482

TEST
Bird-Dropping: 25
Dusty: 149
Normal: 278
Surface-Damage: 33
TOTAL: 485

Saved to: /content/solarguard_v3_combined

```

## Cell 44 [code]

```python
import tensorflow as tf
import numpy as np
from pathlib import Path

DATASET_V3 = Path("/content/solarguard_v3_combined")

CLASS_NAMES_V3 = [
    "Bird-Dropping",
    "Dusty",
    "Normal",
    "Surface-Damage"
]

IMG_SIZE = (224, 224)
BATCH_SIZE = 32
SEED = 42

train_ds_v3 = tf.keras.utils.image_dataset_from_directory(
    DATASET_V3 / "train",
    class_names=CLASS_NAMES_V3,
    label_mode="int",
    image_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    shuffle=True,
    seed=SEED
)

val_ds_v3 = tf.keras.utils.image_dataset_from_directory(
    DATASET_V3 / "val",
    class_names=CLASS_NAMES_V3,
    label_mode="int",
    image_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    shuffle=False
)

test_ds_v3 = tf.keras.utils.image_dataset_from_directory(
    DATASET_V3 / "test",
    class_names=CLASS_NAMES_V3,
    label_mode="int",
    image_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    shuffle=False
)

counts_v3 = np.array([
    len(list((DATASET_V3 / "train" / name).glob("*")))
    for name in CLASS_NAMES_V3
], dtype=np.float32)

class_weights_v3 = {
    i: float(counts_v3.sum() / (4 * count))
    for i, count in enumerate(counts_v3)
}

AUTOTUNE = tf.data.AUTOTUNE

train_ds_v3 = train_ds_v3.prefetch(AUTOTUNE)
val_ds_v3 = val_ds_v3.prefetch(AUTOTUNE)
test_ds_v3 = test_ds_v3.prefetch(AUTOTUNE)

print("\nTraining counts:", counts_v3.astype(int).tolist())
print("Class weights:", class_weights_v3)
print("GPU:", tf.config.list_physical_devices("GPU"))
print("\nV3 datasets loaded successfully.")
```

**Outputs:**

```
Found 2251 files belonging to 4 classes.
Found 482 files belonging to 4 classes.
Found 485 files belonging to 4 classes.

Training counts: [116, 690, 1294, 151]
Class weights: {0: 4.851293087005615, 1: 0.8155797123908997, 2: 0.43489181995391846, 3: 3.726821184158325}
GPU: [PhysicalDevice(name='/physical_device:GPU:0', device_type='GPU')]

V3 datasets loaded successfully.

```

## Cell 45 [code]

```python
import tensorflow as tf
from tensorflow.keras import layers, Model
from tensorflow.keras.applications import MobileNetV2

tf.keras.utils.set_random_seed(42)

# 1. Training-only augmentation
augmentation_v3 = tf.keras.Sequential([
    layers.RandomFlip("horizontal"),
    layers.RandomRotation(0.08),
    layers.RandomZoom(0.10),
    layers.RandomContrast(0.10),
], name="augmentation_v3")

# 2. Pretrained MobileNetV2 backbone
backbone_v3 = MobileNetV2(
    input_shape=(224, 224, 3),
    include_top=False,
    weights="imagenet"
)

backbone_v3.trainable = False

# 3. Build the classification model
inputs_v3 = layers.Input(
    shape=(224, 224, 3),
    name="image_input"
)

x = augmentation_v3(inputs_v3)

# Input images are RGB pixels in the range 0–255.
# Preprocessing is included inside the saved model.
x = layers.Rescaling(
    scale=1.0 / 127.5,
    offset=-1
)(x)

x = backbone_v3(x, training=False)

x = layers.GlobalAveragePooling2D()(x)
x = layers.Dropout(0.35)(x)

outputs_v3 = layers.Dense(
    4,
    activation="softmax",
    name="predictions"
)(x)

model_v3 = Model(
    inputs_v3,
    outputs_v3,
    name="SolarGuard_V3"
)

# 4. Compile
model_v3.compile(
    optimizer=tf.keras.optimizers.Adam(
        learning_rate=0.0003
    ),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"]
)

# 5. Save best model automatically
checkpoint_v3 = "/content/solarguard_v3_best.keras"

callbacks_v3 = [
    tf.keras.callbacks.ModelCheckpoint(
        filepath=checkpoint_v3,
        monitor="val_loss",
        save_best_only=True,
        verbose=1
    ),
    tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=5,
        restore_best_weights=True
    ),
    tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=2,
        min_lr=1e-6
    )
]

print("Starting SolarGuard Version 3 training...")

history_v3 = model_v3.fit(
    train_ds_v3,
    validation_data=val_ds_v3,
    epochs=20,
    class_weight=class_weights_v3,
    callbacks=callbacks_v3
)

print("\nVersion 3 training completed.")
print("Best checkpoint:", checkpoint_v3)
```

**Outputs:**

```
Starting SolarGuard Version 3 training...
Epoch 1/20
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m0s[0m 128ms/step - accuracy: 0.3459 - loss: 1.7553
Epoch 1: val_loss improved from None to 1.27902, saving model to /content/solarguard_v3_best.keras

Epoch 1: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m26s[0m 183ms/step - accuracy: 0.4176 - loss: 1.6193 - val_accuracy: 0.4502 - val_loss: 1.2790 - learning_rate: 3.0000e-04
Epoch 2/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 121ms/step - accuracy: 0.5342 - loss: 1.2917
Epoch 2: val_loss improved from 1.27902 to 0.99797, saving model to /content/solarguard_v3_best.keras

Epoch 2: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m11s[0m 153ms/step - accuracy: 0.5762 - loss: 1.2536 - val_accuracy: 0.6390 - val_loss: 0.9980 - learning_rate: 3.0000e-04
Epoch 3/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 122ms/step - accuracy: 0.6354 - loss: 1.0764
Epoch 3: val_loss improved from 0.99797 to 0.90304, saving model to /content/solarguard_v3_best.keras

Epoch 3: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m11s[0m 153ms/step - accuracy: 0.6593 - loss: 1.0388 - val_accuracy: 0.6846 - val_loss: 0.9030 - learning_rate: 3.0000e-04
Epoch 4/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 120ms/step - accuracy: 0.6684 - loss: 0.9305
Epoch 4: val_loss improved from 0.90304 to 0.80146, saving model to /content/solarguard_v3_best.keras

Epoch 4: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m11s[0m 151ms/step - accuracy: 0.6997 - loss: 0.9051 - val_accuracy: 0.7178 - val_loss: 0.8015 - learning_rate: 3.0000e-04
Epoch 5/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 115ms/step - accuracy: 0.7007 - loss: 0.8826
Epoch 5: val_loss improved from 0.80146 to 0.72287, saving model to /content/solarguard_v3_best.keras

Epoch 5: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m12s[0m 159ms/step - accuracy: 0.7170 - loss: 0.8819 - val_accuracy: 0.7427 - val_loss: 0.7229 - learning_rate: 3.0000e-04
Epoch 6/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 119ms/step - accuracy: 0.7095 - loss: 0.8607
Epoch 6: val_loss improved from 0.72287 to 0.65376, saving model to /content/solarguard_v3_best.keras

Epoch 6: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m12s[0m 163ms/step - accuracy: 0.7259 - loss: 0.8355 - val_accuracy: 0.7614 - val_loss: 0.6538 - learning_rate: 3.0000e-04
Epoch 7/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 120ms/step - accuracy: 0.7472 - loss: 0.7978
Epoch 7: val_loss improved from 0.65376 to 0.63818, saving model to /content/solarguard_v3_best.keras

Epoch 7: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m11s[0m 152ms/step - accuracy: 0.7530 - loss: 0.7919 - val_accuracy: 0.7676 - val_loss: 0.6382 - learning_rate: 3.0000e-04
Epoch 8/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 115ms/step - accuracy: 0.7455 - loss: 0.7492
Epoch 8: val_loss improved from 0.63818 to 0.60052, saving model to /content/solarguard_v3_best.keras

Epoch 8: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m11s[0m 155ms/step - accuracy: 0.7561 - loss: 0.7301 - val_accuracy: 0.7822 - val_loss: 0.6005 - learning_rate: 3.0000e-04
Epoch 9/20
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m0s[0m 131ms/step - accuracy: 0.7386 - loss: 0.7613
Epoch 9: val_loss improved from 0.60052 to 0.57325, saving model to /content/solarguard_v3_best.keras

Epoch 9: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m12s[0m 163ms/step - accuracy: 0.7632 - loss: 0.7102 - val_accuracy: 0.7925 - val_loss: 0.5733 - learning_rate: 3.0000e-04
Epoch 10/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 122ms/step - accuracy: 0.7455 - loss: 0.6879
Epoch 10: val_loss improved from 0.57325 to 0.52731, saving model to /content/solarguard_v3_best.keras

Epoch 10: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m11s[0m 153ms/step - accuracy: 0.7663 - loss: 0.6668 - val_accuracy: 0.8133 - val_loss: 0.5273 - learning_rate: 3.0000e-04
Epoch 11/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 120ms/step - accuracy: 0.7675 - loss: 0.6765
Epoch 11: val_loss improved from 0.52731 to 0.51500, saving model to /content/solarguard_v3_best.keras

Epoch 11: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m12s[0m 164ms/step - accuracy: 0.7788 - loss: 0.6524 - val_accuracy: 0.8112 - val_loss: 0.5150 - learning_rate: 3.0000e-04
Epoch 12/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 121ms/step - accuracy: 0.7878 - loss: 0.6163
Epoch 12: val_loss improved from 0.51500 to 0.51284, saving model to /content/solarguard_v3_best.keras

Epoch 12: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m12s[0m 165ms/step - accuracy: 0.8014 - loss: 0.6270 - val_accuracy: 0.8112 - val_loss: 0.5128 - learning_rate: 3.0000e-04
Epoch 13/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 121ms/step - accuracy: 0.7819 - loss: 0.6632
Epoch 13: val_loss improved from 0.51284 to 0.45192, saving model to /content/solarguard_v3_best.keras

Epoch 13: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m12s[0m 165ms/step - accuracy: 0.8001 - loss: 0.6173 - val_accuracy: 0.8299 - val_loss: 0.4519 - learning_rate: 3.0000e-04
Epoch 14/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 117ms/step - accuracy: 0.8036 - loss: 0.5916
Epoch 14: val_loss did not improve from 0.45192
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m10s[0m 140ms/step - accuracy: 0.8085 - loss: 0.5820 - val_accuracy: 0.8154 - val_loss: 0.4810 - learning_rate: 3.0000e-04
Epoch 15/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 120ms/step - accuracy: 0.7860 - loss: 0.6207
Epoch 15: val_loss did not improve from 0.45192
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m10s[0m 144ms/step - accuracy: 0.8041 - loss: 0.6060 - val_accuracy: 0.8216 - val_loss: 0.4586 - learning_rate: 3.0000e-04
Epoch 16/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 119ms/step - accuracy: 0.8146 - loss: 0.5315
Epoch 16: val_loss did not improve from 0.45192
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m10s[0m 143ms/step - accuracy: 0.8170 - loss: 0.5664 - val_accuracy: 0.8278 - val_loss: 0.4550 - learning_rate: 1.5000e-04
Epoch 17/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 119ms/step - accuracy: 0.7993 - loss: 0.5618
Epoch 17: val_loss improved from 0.45192 to 0.44733, saving model to /content/solarguard_v3_best.keras

Epoch 17: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m12s[0m 163ms/step - accuracy: 0.8076 - loss: 0.5674 - val_accuracy: 0.8257 - val_loss: 0.4473 - learning_rate: 1.5000e-04
Epoch 18/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 126ms/step - accuracy: 0.8195 - loss: 0.5395
Epoch 18: val_loss improved from 0.44733 to 0.42869, saving model to /content/solarguard_v3_best.keras

Epoch 18: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m12s[0m 171ms/step - accuracy: 0.8250 - loss: 0.5301 - val_accuracy: 0.8361 - val_loss: 0.4287 - learning_rate: 1.5000e-04
Epoch 19/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 121ms/step - accuracy: 0.8038 - loss: 0.6422
Epoch 19: val_loss improved from 0.42869 to 0.41279, saving model to /content/solarguard_v3_best.keras

Epoch 19: finished saving model to /content/solarguard_v3_best.keras
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m12s[0m 165ms/step - accuracy: 0.8223 - loss: 0.5773 - val_accuracy: 0.8382 - val_loss: 0.4128 - learning_rate: 1.5000e-04
Epoch 20/20
[1m70/71[0m [32m━━━━━━━━━━━━━━━━━━━[0m[37m━[0m [1m0s[0m 119ms/step - accuracy: 0.7964 - loss: 0.5878
Epoch 20: val_loss did not improve from 0.41279
[1m71/71[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m10s[0m 142ms/step - accuracy: 0.8170 - loss: 0.5617 - val_accuracy: 0.8340 - val_loss: 0.4224 - learning_rate: 1.5000e-04

Version 3 training completed.
Best checkpoint: /content/solarguard_v3_best.keras

```

## Cell 46 [code]

```python
import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt

from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    f1_score
)

# Load the best checkpoint from epoch 19
best_v3 = tf.keras.models.load_model(
    "/content/solarguard_v3_best.keras"
)

# Evaluate on the 485 V3 test images
test_loss, test_accuracy = best_v3.evaluate(
    test_ds_v3,
    verbose=1
)

# Generate predictions
probabilities = best_v3.predict(
    test_ds_v3,
    verbose=1
)

y_pred = np.argmax(probabilities, axis=1)

# True labels (test_ds_v3 uses shuffle=False)
y_true = np.concatenate([
    labels.numpy()
    for images, labels in test_ds_v3
])

macro_f1 = f1_score(
    y_true,
    y_pred,
    average="macro",
    zero_division=0
)

print("\n" + "=" * 48)
print("SOLARGUARD VERSION 3 — TEST RESULTS")
print("=" * 48)

print(f"Test accuracy: {test_accuracy * 100:.2f}%")
print(f"Test loss: {test_loss:.4f}")
print(f"Macro F1-score: {macro_f1:.3f}")

print("\nClassification report:")
print(
    classification_report(
        y_true,
        y_pred,
        labels=list(range(4)),
        target_names=CLASS_NAMES_V3,
        digits=3,
        zero_division=0
    )
)

cm = confusion_matrix(
    y_true,
    y_pred,
    labels=list(range(4))
)

fig, ax = plt.subplots(figsize=(8, 7))

disp = ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=CLASS_NAMES_V3
)

disp.plot(
    ax=ax,
    cmap="Blues",
    values_format="d",
    colorbar=False
)

plt.title("SolarGuard V3 — Test Confusion Matrix")
plt.xticks(rotation=25, ha="right")
plt.tight_layout()
plt.show()
```

**Outputs:**

```
[1m16/16[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m6s[0m 126ms/step - accuracy: 0.8536 - loss: 0.3916
[1m16/16[0m [32m━━━━━━━━━━━━━━━━━━━━[0m[37m[0m [1m4s[0m 150ms/step

================================================
SOLARGUARD VERSION 3 — TEST RESULTS
================================================
Test accuracy: 85.36%
Test loss: 0.3916
Macro F1-score: 0.758

Classification report:
                precision    recall  f1-score   support

 Bird-Dropping      0.386     0.880     0.537        25
         Dusty      0.893     0.732     0.804       149
        Normal      0.959     0.921     0.939       278
Surface-Damage      0.692     0.818     0.750        33

      accuracy                          0.854       485
     macro avg      0.733     0.838     0.758       485
  weighted avg      0.891     0.854     0.864       485

<Figure size 800x700 with 1 Axes>
```

## Cell 47 [code]

```python
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_recall_fscore_support
)

# Uses probabilities and y_true from your V3 evaluation cell.
# Bird-Dropping is class index 0.

print("Threshold | Accuracy | Macro F1 | Bird Precision | Bird Recall")
print("-" * 65)

for threshold in [0.00, 0.30, 0.40, 0.50, 0.60, 0.70]:
    adjusted = probabilities.copy()

    # If Bird-Dropping's score is below the threshold,
    # prevent it from winning the final prediction.
    adjusted[adjusted[:, 0] < threshold, 0] = -1

    predictions = np.argmax(adjusted, axis=1)

    accuracy = accuracy_score(y_true, predictions)
    macro_f1 = f1_score(
        y_true,
        predictions,
        average="macro",
        zero_division=0
    )

    precision, recall, _, _ = precision_recall_fscore_support(
        y_true,
        predictions,
        labels=[0, 1, 2, 3],
        zero_division=0
    )

    print(
        f"{threshold:9.2f} | "
        f"{accuracy:8.3f} | "
        f"{macro_f1:8.3f} | "
        f"{precision[0]:14.3f} | "
        f"{recall[0]:11.3f}"
    )
```

**Outputs:**

```
Threshold | Accuracy | Macro F1 | Bird Precision | Bird Recall
-----------------------------------------------------------------
     0.00 |    0.854 |    0.758 |          0.386 |       0.880
     0.30 |    0.854 |    0.758 |          0.386 |       0.880
     0.40 |    0.856 |    0.759 |          0.400 |       0.880
     0.50 |    0.866 |    0.773 |          0.478 |       0.880
     0.60 |    0.854 |    0.732 |          0.417 |       0.600
     0.70 |    0.860 |    0.738 |          0.481 |       0.520

```

## Cell 48 [code]

```python
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_recall_fscore_support
)

# Generate predictions on validation images
val_probabilities = best_v3.predict(
    val_ds_v3,
    verbose=0
)

val_true = np.concatenate([
    labels.numpy()
    for images, labels in val_ds_v3
])

thresholds = np.arange(0.30, 0.76, 0.05)

results = []

print(
    "Threshold | Accuracy | Macro F1 | "
    "Bird Precision | Bird Recall"
)
print("-" * 65)

for threshold in thresholds:
    adjusted = val_probabilities.copy()

    adjusted[adjusted[:, 0] < threshold, 0] = -1

    predictions = np.argmax(adjusted, axis=1)

    accuracy = accuracy_score(val_true, predictions)
    macro_f1 = f1_score(
        val_true,
        predictions,
        average="macro",
        zero_division=0
    )

    precision, recall, _, _ = (
        precision_recall_fscore_support(
            val_true,
            predictions,
            labels=[0, 1, 2, 3],
            zero_division=0
        )
    )

    results.append({
        "threshold": float(threshold),
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "bird_precision": precision[0],
        "bird_recall": recall[0]
    })

    print(
        f"{threshold:9.2f} | "
        f"{accuracy:8.3f} | "
        f"{macro_f1:8.3f} | "
        f"{precision[0]:14.3f} | "
        f"{recall[0]:11.3f}"
    )

best_result = max(
    results,
    key=lambda x: x["macro_f1"]
)

BEST_BIRD_THRESHOLD = best_result["threshold"]

print("\nBest validation threshold:",
      round(BEST_BIRD_THRESHOLD, 2))
print("Best validation macro F1:",
      round(best_result["macro_f1"], 3))
```

**Outputs:**

```
Threshold | Accuracy | Macro F1 | Bird Precision | Bird Recall
-----------------------------------------------------------------
     0.30 |    0.838 |    0.692 |          0.281 |       0.640
     0.35 |    0.838 |    0.692 |          0.281 |       0.640
     0.40 |    0.842 |    0.696 |          0.296 |       0.640
     0.45 |    0.846 |    0.701 |          0.320 |       0.640
     0.50 |    0.853 |    0.712 |          0.340 |       0.640
     0.55 |    0.861 |    0.721 |          0.375 |       0.600
     0.60 |    0.865 |    0.717 |          0.419 |       0.520
     0.65 |    0.871 |    0.727 |          0.545 |       0.480
     0.70 |    0.876 |    0.727 |          0.611 |       0.440
     0.75 |    0.878 |    0.722 |          0.692 |       0.360

Best validation threshold: 0.7
Best validation macro F1: 0.727

```

## Cell 49 [code]

```python
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay
)
import matplotlib.pyplot as plt

# Threshold selected from validation data
threshold = BEST_BIRD_THRESHOLD

# Use V3 test predictions from our earlier evaluation
# Recompute to ensure we are using the correct model
test_probs = best_v3.predict(test_ds_v3, verbose=0)

test_true = np.concatenate([
    labels.numpy()
    for images, labels in test_ds_v3
])

# Original predictions
original_predictions = np.argmax(test_probs, axis=1)

# Apply Bird-Dropping threshold
adjusted_probs = test_probs.copy()
adjusted_probs[adjusted_probs[:, 0] < threshold, 0] = -1

adjusted_predictions = np.argmax(adjusted_probs, axis=1)

print("SOLARGUARD V3 — FINAL TEST COMPARISON")
print("-" * 45)

for name, predictions in [
    ("Original V3", original_predictions),
    ("Threshold-adjusted V3", adjusted_predictions)
]:
    print(f"\n{name}")
    print(
        "Accuracy:",
        round(accuracy_score(test_true, predictions) * 100, 2),
        "%"
    )
    print(
        "Macro F1:",
        round(f1_score(
            test_true,
            predictions,
            average="macro",
            zero_division=0
        ), 3)
    )

print("\nCLASSIFICATION REPORT — THRESHOLD ADJUSTED")
print(
    classification_report(
        test_true,
        adjusted_predictions,
        labels=[0, 1, 2, 3],
        target_names=CLASS_NAMES_V3,
        digits=3,
        zero_division=0
    )
)

cm = confusion_matrix(
    test_true,
    adjusted_predictions,
    labels=[0, 1, 2, 3]
)

fig, ax = plt.subplots(figsize=(8, 7))

ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=CLASS_NAMES_V3
).plot(
    ax=ax,
    cmap="Blues",
    values_format="d",
    colorbar=False
)

plt.title("SolarGuard V3 — Threshold-Adjusted Test Results")
plt.xticks(rotation=25, ha="right")
plt.tight_layout()
plt.show()
```

**Outputs:**

```
SOLARGUARD V3 — FINAL TEST COMPARISON
---------------------------------------------

Original V3
Accuracy: 85.36 %
Macro F1: 0.758

Threshold-adjusted V3
Accuracy: 85.98 %
Macro F1: 0.738

CLASSIFICATION REPORT — THRESHOLD ADJUSTED
                precision    recall  f1-score   support

 Bird-Dropping      0.481     0.520     0.500        25
         Dusty      0.860     0.785     0.821       149
        Normal      0.945     0.932     0.938       278
Surface-Damage      0.583     0.848     0.691        33

      accuracy                          0.860       485
     macro avg      0.718     0.771     0.738       485
  weighted avg      0.871     0.860     0.863       485

<Figure size 800x700 with 1 Axes>
```

## Cell 50 [code]

```python
import json
import shutil
from pathlib import Path
from google.colab import drive

drive.mount("/content/drive")

save_dir = Path("/content/drive/MyDrive/SolarGuard_Model")
save_dir.mkdir(parents=True, exist_ok=True)

source_model = Path("/content/solarguard_v3_best.keras")
model_path = save_dir / "solarguard_model_v3.keras"
metadata_path = save_dir / "model_metadata_v3.json"

# Copy the best V3 checkpoint; do not overwrite V1 or V2
shutil.copy2(source_model, model_path)

metadata = {
    "model_version": "3.0",
    "architecture": "MobileNetV2",
    "class_names": [
        "Bird-Dropping",
        "Dusty",
        "Normal",
        "Surface-Damage"
    ],
    "image_size": [224, 224],
    "input_color_mode": "RGB",
    "input_pixel_range": [0, 255],
    "preprocessing": "Built into model: Rescaling(1/127.5, offset=-1)",
    "decision_rule": "argmax",
    "bird_dropping_threshold": None,
    "test_accuracy": 0.8536,
    "macro_f1": 0.758,
    "test_images": 485,
    "note": (
        "Preliminary experimental evaluation. "
        "Potential near-duplicates and synthetic images remain. "
        "Not validated for real-world safety-critical inspection."
    )
}

with open(metadata_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=4)

print("V3 model saved:", model_path)
print("V3 metadata saved:", metadata_path)
print("Model size:", round(model_path.stat().st_size / (1024**2), 2), "MB")
```

**Outputs:**

```
Drive already mounted at /content/drive; to attempt to forcibly remount, call drive.mount("/content/drive", force_remount=True).
V3 model saved: /content/drive/MyDrive/SolarGuard_Model/solarguard_model_v3.keras
V3 metadata saved: /content/drive/MyDrive/SolarGuard_Model/model_metadata_v3.json
Model size: 9.25 MB

```

