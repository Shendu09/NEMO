#!/bin/bash
# NEMO CLI Automation: Open Chrome, Jupyter, and PyCharm

echo "🚀 NEMO OS Automation - Multi-App Demo"
echo "======================================="

# Method 1: Using NEMO's --task CLI (simpler)
echo "Starting automation with NEMO CLI..."

# Open Chrome with Profile 1
python clevrr_service.py run --task "open chrome with profile 1"

# Open Jupyter
python clevrr_service.py run --task "open jupyter notebook"

# Open PyCharm
python clevrr_service.py run --task "open pycharm"

# Type code
python clevrr_service.py run --task "type def hello(): print('NEMO automation')"

echo "✓ All applications opened and code entered!"
