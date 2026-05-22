#!/bin/bash
set -e

PACMAN_PKGS=(wl-clipboard python-requests python-gobject)
PIP_PKG="duckduckgo_search"
MODEL="${1:-qwen2.5:3b-instruct}"

if ! command -v pacman &>/dev/null; then
  echo "Этот скрипт рассчитан на Arch Linux (pacman)."
  exit 1
fi

echo "=== Установка пакетов pacman ==="
sudo pacman -Sy --needed "${PACMAN_PKGS[@]}"

echo ""
echo "=== Установка python-пакетов ==="
pip install "$PIP_PKG"

echo ""
echo "=== Ollama ==="
if command -v ollama &>/dev/null; then
  if ! ollama list 2>/dev/null | grep -q "$MODEL"; then
    echo "Качаю модель $MODEL..."
    ollama pull "$MODEL"
  else
    echo "Модель $MODEL уже загружена."
  fi
else
  echo "Ollama не найден. Установи вручную: https://ollama.com"
fi

echo ""
echo "=== Права ==="
chmod +x "$(dirname "$0")/ai-assist.py" "$(dirname "$0")/toggle-ai-assist.sh"

echo ""
echo "Готово. Модель: $MODEL"
echo ""
echo "Не забудь указать название модели в ai-assist.py:"
echo "  MODEL = '$MODEL'"
echo ""
echo "Далее добавь в конфиг Hyprland:"
echo ""
echo "  ~/.config/hypr/hyprland/rules.conf:"
echo "    windowrule = float true, match:class ai-assist"
echo "    windowrule = dim_around true, match:class ai-assist"
echo "    windowrule = animation slide, match:class ai-assist"
echo ""
echo "  ~/.config/hypr/hyprland/keybinds.conf:"
echo "    bind = Super+Shift, A, exec, $(dirname "$0")/toggle-ai-assist.sh"
