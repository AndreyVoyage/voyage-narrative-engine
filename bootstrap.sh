#!/bin/bash
echo "📥 Скачивание скрипта интеграции..."
curl -L "https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/unpack-and-integrate-v1.2-full.sh" -o /tmp/voyage-unpack.sh 2>/dev/null
if [[ -f "/tmp/voyage-unpack.sh" ]] && [[ -s "/tmp/voyage-unpack.sh" ]]; then
    chmod +x /tmp/voyage-unpack.sh
    bash /tmp/voyage-unpack.sh
else
    echo "❌ Не удалось скачать. Загрузите вручную."
fi
