@echo off
pyinstaller --noconfirm --clean --windowed --onedir --name TestGeneratorStudio --add-data "presets;presets" main.py
