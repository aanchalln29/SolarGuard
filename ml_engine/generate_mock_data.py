"""
SolarGuard — Demo Mock Data & Sample Test Image Generator

Seeds the SQLite database with:
1. Superuser account (`admin` with secure environment password)
2. Realistic Solar Panels with operational telemetry
3. Maintenance log records
4. Generated sample solar panel test images (Normal, Dusty, Bird-Dropping, Cracked)
5. Initial inspection runs to populate dashboard metrics and Chart.js charts
"""

import os
import sys
import datetime
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarguard_project.settings')

import django
django.setup()

from django.contrib.auth.models import User
from django.core.files import File
from core.models import Panel, Inspection, MaintenanceLog
from ml_engine.predictor import predict_fault, predict_degradation
from ml_engine.train_rf import MODEL_PATH as RF_MODEL_PATH, train_and_evaluate as train_rf_model
from ml_engine.train_vision import VISION_MODEL_PATH, train_vision_model


def create_sample_panel_image(category, output_path):
    """
    Synthesize realistic solar cell textures with simulated faults for quick testing.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new('RGB', (256, 256), color=(20, 40, 80))
    draw = ImageDraw.Draw(img)

    # Draw solar cell grid lines
    grid_color = (180, 200, 230)
    for x in range(0, 256, 64):
        draw.line([(x, 0), (x, 256)], fill=grid_color, width=2)
    for y in range(0, 256, 64):
        draw.line([(0, y), (256, y)], fill=grid_color, width=2)

    # Busbars
    for x in [32, 96, 160, 224]:
        draw.line([(x, 0), (x, 256)], fill=(220, 220, 220), width=1)

    if category == 'dusty':
        # Add dull yellow/brown tint overlay
        dust_overlay = Image.new('RGB', (256, 256), color=(180, 160, 110))
        img = Image.blend(img, dust_overlay, alpha=0.45)
    elif category == 'bird_drop':
        # Draw white/brown opaque spots
        for cx, cy, r in [(70, 80, 22), (85, 95, 14), (180, 170, 28), (195, 155, 12)]:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(245, 245, 240), outline=(139, 69, 19), width=2)
    elif category == 'cracked':
        # Draw jagged lightning-like crack lines
        crack_points = [(30, 20), (70, 90), (120, 110), (160, 180), (220, 240)]
        for i in range(len(crack_points) - 1):
            draw.line([crack_points[i], crack_points[i + 1]], fill=(255, 255, 255), width=3)
            # Branch crack
            draw.line([crack_points[i], (crack_points[i][0] + 25, crack_points[i][1] + 15)], fill=(240, 240, 240), width=2)

    img.save(output_path, 'JPEG', quality=90)
    return output_path


def seed_database():
    print("=" * 70)
    print("[SolarGuard] Seeding Demo Database & Sample Test Assets")
    print("=" * 70)

    # 1. Train RF model if not already generated
    if not RF_MODEL_PATH.exists():
        print("[*] Training initial Random Forest degradation model...")
        train_rf_model(n_samples=2000)

    # 2. Train Vision Classifier if not already generated
    if not VISION_MODEL_PATH.exists():
        print("[*] Training initial Computer Vision fault classifier...")
        train_vision_model()

    # 2. Superuser creation
    if not User.objects.filter(username='admin').exists():
        admin_pwd = os.environ.get('SOLARGUARD_ADMIN_PASSWORD', 'SolarGuard#Sec2026!')
        User.objects.create_superuser('admin', 'admin@solarguard.local', admin_pwd)
        print("[OK] Created default superuser: admin (password configured via SOLARGUARD_ADMIN_PASSWORD or default development secret).")
    else:
        print("[*] Superuser 'admin' already exists.")

    # 3. Create Sample Solar Panels
    today = datetime.date.today()
    panels_data = [
        {
            'serial_number': 'SG-ARRAY-A101',
            'site_location': 'Rooftop Array Block A (South-Facing)',
            'install_date': today - datetime.timedelta(days=365 * 4 + 60),  # ~4.2 years
            'last_cleaned_date': today - datetime.timedelta(days=95),
            'avg_temp_exposure': 38.5,
            'dust_index_avg': 0.72,
        },
        {
            'serial_number': 'SG-ARRAY-A102',
            'site_location': 'Rooftop Array Block A (South-Facing)',
            'install_date': today - datetime.timedelta(days=365 * 1 + 30),  # ~1.1 years
            'last_cleaned_date': today - datetime.timedelta(days=12),
            'avg_temp_exposure': 28.0,
            'dust_index_avg': 0.20,
        },
        {
            'serial_number': 'SG-ARRAY-B204',
            'site_location': 'Ground Mount Array Zone 2 (Inverter #3)',
            'install_date': today - datetime.timedelta(days=365 * 6 + 120), # ~6.3 years
            'last_cleaned_date': today - datetime.timedelta(days=140),
            'avg_temp_exposure': 44.0,
            'dust_index_avg': 0.85,
        },
        {
            'serial_number': 'SG-ARRAY-C301',
            'site_location': 'Carport Canopy West Section',
            'install_date': today - datetime.timedelta(days=365 * 2),       # ~2 years
            'last_cleaned_date': today - datetime.timedelta(days=35),
            'avg_temp_exposure': 32.0,
            'dust_index_avg': 0.40,
        },
        {
            'serial_number': 'SG-ARRAY-D405',
            'site_location': 'Agrivoltaic Experimental Field 4',
            'install_date': today - datetime.timedelta(days=365 * 8),       # ~8 years
            'last_cleaned_date': today - datetime.timedelta(days=180),
            'avg_temp_exposure': 46.5,
            'dust_index_avg': 0.90,
        },
        {
            'serial_number': 'SG-ARRAY-E502',
            'site_location': 'Industrial Warehouse Rooftop Sector 5',
            'install_date': today - datetime.timedelta(days=180),           # 6 months
            'last_cleaned_date': today - datetime.timedelta(days=8),
            'avg_temp_exposure': 27.5,
            'dust_index_avg': 0.15,
        },
    ]

    panels = []
    for pdata in panels_data:
        p, created = Panel.objects.get_or_create(
            serial_number=pdata['serial_number'],
            defaults=pdata
        )
        panels.append(p)
        status_str = "Created" if created else "Exists"
        print(f"[*] Panel {p.serial_number}: {status_str}")

    # 4. Generate Sample Test Images
    sample_images_dir = BASE_DIR / 'media' / 'sample_test_images'
    sample_images_dir.mkdir(parents=True, exist_ok=True)

    test_files = {
        'normal': create_sample_panel_image('normal', sample_images_dir / 'sample_normal.jpg'),
        'dusty': create_sample_panel_image('dusty', sample_images_dir / 'sample_dusty.jpg'),
        'bird_drop': create_sample_panel_image('bird_drop', sample_images_dir / 'sample_bird_drop.jpg'),
        'cracked': create_sample_panel_image('cracked', sample_images_dir / 'sample_cracked.jpg'),
    }
    print("[OK] Generated 4 sample test images in media/sample_test_images/")

    # 5. Seed Maintenance Logs
    MaintenanceLog.objects.get_or_create(
        panel=panels[0],
        action_type='cleaning',
        performed_at=today - datetime.timedelta(days=95),
        defaults={'notes': 'Semi-annual demineralized water high-pressure spray.'}
    )
    MaintenanceLog.objects.get_or_create(
        panel=panels[2],
        action_type='repair',
        performed_at=today - datetime.timedelta(days=140),
        defaults={'notes': 'Replaced cracked junction box sealant and tightened mounting clamp.'}
    )
    MaintenanceLog.objects.get_or_create(
        panel=panels[4],
        action_type='replacement',
        performed_at=today - datetime.timedelta(days=220),
        defaults={'notes': 'Replaced bypass diode #2 after localized hotspot event.'}
    )
    print("[OK] Seeded maintenance log entries.")

    # 6. Seed Sample Inspections if table is empty
    if Inspection.objects.count() == 0:
        print("[*] Running initial demo inspections through Dual-ML inference pipeline...")
        inspection_configs = [
            (panels[0], test_files['dusty'], "Drone automated pass. Moderate dust buildup observed."),
            (panels[1], test_files['normal'], "Routine monthly post-wash verification."),
            (panels[2], test_files['cracked'], "High inverter power drop detected, thermal scan requested."),
            (panels[3], test_files['bird_drop'], "Localized tree canopy shading and bird droppings."),
            (panels[4], test_files['cracked'], "Aging array module inspection after heavy storm."),
            (panels[5], test_files['normal'], "Commissioning baseline inspection.")
        ]

        for p, img_path, note in inspection_configs:
            with open(img_path, 'rb') as f:
                ins = Inspection(
                    panel=p,
                    predicted_class="Analyzing...",
                    confidence_score=0.0,
                    degradation_probability=0.0,
                    risk_category="Low",
                    notes=note
                )
                ins.image.save(img_path.name, File(f), save=False)
                ins.save()

                # Run inference
                fault_res = predict_fault(ins.image.path)
                deg_res = predict_degradation(p)

                ins.predicted_class = fault_res['predicted_class']
                ins.confidence_score = fault_res['confidence_score']
                ins.degradation_probability = deg_res['degradation_probability']
                ins.risk_category = deg_res['risk_category']
                ins.notes = f"{note}\n[Inference: {fault_res['engine']} | {deg_res['engine']}]"
                ins.save()

        print(f"[OK] Seeded {len(inspection_configs)} initial inspection records.")

    print("=" * 70)
    print("[OK] Demo dataset initialization complete!")
    print("=" * 70)


if __name__ == '__main__':
    seed_database()
