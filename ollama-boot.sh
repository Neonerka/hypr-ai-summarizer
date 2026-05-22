#!/bin/bash
set -e

echo "=== Настройка автозапуска Ollama и предзагрузки модели ==="

# 1. Override: держать модель в памяти вечно
echo "Добавляю OLLAMA_KEEP_ALIVE=-1..."
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/keep-model.conf << 'OVERRIDE'
[Service]
Environment=OLLAMA_KEEP_ALIVE=-1
OVERRIDE

# 2. Перезапуск ollama
sudo systemctl daemon-reload
sudo systemctl restart ollama
sudo systemctl enable ollama

# 3. Сервис предзагрузки модели при старте системы
echo "Создаю сервис preload-qwen..."
sudo tee /etc/systemd/system/ollama-preload.service << 'SERVICE'
[Unit]
Description=Preload qwen2.5:3b-instruct into Ollama
After=ollama.service
Requires=ollama.service

[Service]
Type=oneshot
ExecStartPre=/usr/bin/sleep 3
ExecStart=/usr/bin/bash -c 'curl -s -X POST http://localhost:11434/api/generate -d "{\"model\":\"qwen2.5:3b-instruct\",\"prompt\":\"\",\"keep_alive\":\"-1\"}" > /dev/null'
User=neonerka

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable ollama-preload.service

echo ""
echo "Готово. Перезагрузи систему или запусти вручную:"
echo "  sudo systemctl start ollama-preload.service"
echo ""
echo "Проверка:"
echo "  systemctl status ollama"
echo "  systemctl status ollama-preload"
