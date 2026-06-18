#!/usr/bin/env bash
# Reproduce the full analysis end-to-end.
set -e
cd "$(dirname "$0")/src"
echo "1/4 Generating synthetic data..."      && python 01_generate_data.py
echo "2/4 EDA + behavioural signals..."       && python 02_eda_signals.py
echo "3/4 Recovery-propensity model..."        && python 03_model.py
echo "4/4 Call-transcript NLP..."              && python 04_text_analytics.py
echo "Done. See outputs/ for charts, scores and dashboard.html"
