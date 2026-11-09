#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

def main():
    """Run administrative tasks."""
    # If invoked under an interpreter without TensorFlow/Django, automatically delegate to .venv
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent
    venv_py = base_dir / '.venv' / 'Scripts' / 'python.exe'
    if venv_py.exists() and sys.executable.lower() != str(venv_py).lower():
        try:
            import tensorflow  # noqa: F401
            import django      # noqa: F401
        except ImportError:
            import subprocess
            sys.exit(subprocess.call([str(venv_py)] + sys.argv))

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarguard_project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
