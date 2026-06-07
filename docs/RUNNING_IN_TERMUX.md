# Запуск Voyage в Termux (Android)

> Пошаговая инструкция для запуска `session_finalize.py` на Android через Termux.

---

## 1. Установка Termux (если ещё нет)

Скачайте Termux из F-Droid (рекомендуется) или GitHub Releases.
**Не используйте Google Play** — версия там устаревшая.

- F-Droid: https://f-droid.org/packages/com.termux/
- GitHub: https://github.com/termux/termux-app/releases

---

## 2. Первоначальная настройка (один раз)

Откройте Termux и выполните:

```bash
# Обновление пакетов
pkg update && pkg upgrade -y

# Установка необходимого
pkg install python3 git -y

# Проверка
python3 --version   # Должно вывести Python 3.8+ или 3.11+
git --version       # Должно вывести git version 2.x
```

Если `python3` не найден — попробуйте `pkg install python` (без цифры).

---

## 3. Клонирование репозитория

```bash
cd ~
git clone https://github.com/AndreyVoyage/voyage-narrative-engine.git

# Проверка
ls voyage-narrative-engine/
# Должно быть: README.md, session_finalize.py, personas/, scenarios/, state/
```

Если репозиторий уже есть — просто обновите:
```bash
cd ~/voyage-narrative-engine
git pull origin main
```

---

## 4. Проверка файлов

```bash
cd ~/voyage-narrative-engine
ls -la

# Должно быть:
# - session_finalize.py (главный скрипт)
# - README.md
# - personas/ (KIRA_MODULE_v14.json, SERGEY_MODULE_v4.json, MARINA_MODULE_v2.json)
# - scenarios/ (SCENARIO_SAUNA_QUARTET.json)
# - state/ (STATE_TEMPLATE_v2.json)
# - scripts/python/check_consistency.py (опционально)
```

Если `session_finalize.py` отсутствует — скачайте его отдельно и положите в папку репозитория.

---

## 5. Подготовка лога сессии

После игровой сессии в LLM (Kimi/DeepSeek/Claude):

### Способ A: Через буфер обмена (если мало текста)

```bash
cd ~/voyage-narrative-engine
mkdir -p sessions/raw
nano sessions/raw/session_2026-06-08.log
```

1. В Termux: зажмите пальцем на экране → "Paste" (вставить)
2. Вставьте весь текст из чата
3. Сохраните: `Ctrl+O` (или `VolumeDown+O`), `Enter`, `Ctrl+X` (или `VolumeDown+X`)

### Способ B: Через файл (если много текста)

Скопируйте файл с компьютера через `scp` или мессенджер:
```bash
# Если файл в Downloads телефона
cp ~/storage/downloads/session_2026-06-08.log ~/voyage-narrative-engine/sessions/raw/
```

**Важно:** лог должен содержать ВЕСЬ диалог — реплики пользователя и ответы LLM.

---

## 6. Запуск session_finalize.py

```bash
cd ~/voyage-narrative-engine

# Базовый запуск
python3 session_finalize.py --log sessions/raw/session_2026-06-08.log --scenario sauna_quartet

# Если не в стандартной папке репозитория
python3 session_finalize.py --log sessions/raw/session_2026-06-08.log --scenario sauna_quartet --repo ~/voyage-narrative-engine

# Без git-commit (если git не настроен)
python3 session_finalize.py --log sessions/raw/session_2026-06-08.log --scenario sauna_quartet --no-git
```

### Что происходит

```
[INFO] === Voyage Session Finalizer v1.0 ===
[INFO] Log: sessions/raw/session_2026-06-08.log
[INFO] Scenario: sauna_quartet
[INFO] Repo: /data/data/com.termux/files/home/voyage-narrative-engine
[INFO] 
[INFO] [1/5] Parsing log...
  Entries: 45
[INFO] 
[INFO] [2/5] State Manager...
  kira: U1-A → U2-B (detected from speech patterns)
  sergey: S1 → S2
  marina: U1-A → U1-B
[INFO] 
[INFO] [3/5] Loading personas...
  Loaded: kira
  Loaded: sergey
  Loaded: marina
  Skipped: maksim (module not found)
[INFO] 
[INFO] [4/5] Narrative Editor...
[INFO] 
[INFO] [5/5] Visual Extractor + Physiognomist...
  Found 6 key moments
[INFO] 
[INFO] Saving outputs for session: session_2026-06-08_23-49
  → sessions/state/STATE_UPDATE_session_2026-06-08_23-49.json
  → sessions/memory/MEMORY_UPDATE_session_2026-06-08_23-49.json
  → sessions/stories/STORY_session_2026-06-08_23-49.md
  → sessions/visuals/VISUAL_PROMPTS_session_2026-06-08_23-49.md
[INFO] 
[INFO] Updating personas...
  Saved persona: personas/KIRA_MODULE_v14.json
  Saved persona: personas/SERGEY_MODULE_v4.json
  Saved persona: personas/MARINA_MODULE_v2.json
[INFO] 
[INFO] Git commit...
  Git commit done
[INFO] 
[INFO] === DONE ===
```

---

## 7. Проверка результатов

```bash
cd ~/voyage-narrative-engine

# Рассказ
cat sessions/stories/STORY_session_2026-06-08_23-49.md

# Или через less (удобнее для длинного текста)
less sessions/stories/STORY_session_2026-06-08_23-49.md

# Промпты для картинок
cat sessions/visuals/VISUAL_PROMPTS_session_2026-06-08_23-49.md

# Обновлённые метрики
cat sessions/state/STATE_UPDATE_session_2026-06-08_23-49.json

# Git-лог
git log -1
```

---

## 8. Генерация картинок (ручная)

Скрипт создаёт промпты, но не отправляет их в API. Скопируйте нужный промпт из `sessions/visuals/` и отправьте в:

- **Qwen Image** — через Qwen Studio или локально
- **Midjourney** — через Discord
- **Stable Diffusion** — через AUTOMATIC1111 / ComfyUI

Пример:
```bash
# Посмотрите промпты
grep -A 20 "Момент 1:" sessions/visuals/VISUAL_PROMPTS_session_2026-06-08_23-49.md
```

---

## 9. Частые ошибки

### Ошибка: `python3: command not found`

```bash
pkg install python3 -y
# Или:
pkg install python -y
```

### Ошибка: `ModuleNotFoundError: No module named 'json'`

Это невозможно — `json` встроен в Python. Скорее всего:
- Вы запускаете не `python3`, а что-то другое
- Файл `session_finalize.py` повреждён (перекачайте)

### Ошибка: `FileNotFoundError: sessions/raw/session_...log`

```bash
# Проверьте путь
ls -la sessions/raw/
# Если файла нет — создайте:
mkdir -p sessions/raw
nano sessions/raw/session_2026-06-08.log
```

### Ошибка: `Persona not found: personas/KIRA_MODULE_v14.json`

```bash
# Проверьте, что репозиторий полный
ls personas/
# Должно быть: KIRA_MODULE_v14.json, SERGEY_MODULE_v4.json, MARINA_MODULE_v2.json

# Если нет — склонируйте заново:
cd ~
rm -rf voyage-narrative-engine
git clone https://github.com/AndreyVoyage/voyage-narrative-engine.git
```

### Ошибка: `git commit failed`

```bash
# Настройте git (один раз)
git config --global user.email "you@example.com"
git config --global user.name "Your Name"

# Или запустите с --no-git
python3 session_finalize.py --log ... --no-git
```

### Ошибка: `Permission denied` при записи файлов

```bash
# Проверьте владельца папки
ls -la ~ | grep voyage
# Должно быть: drwxr-xr-x ... u0_aXXX u0_aXXX

# Если нет — исправьте:
chmod -R u+rw ~/voyage-narrative-engine
```

---

## 10. Что делать с check_consistency.py

Это **опциональная заглушка** для проверки консистентности лиц.

**Когда использовать:**
- Сгенерировали картинку Киры
- Хотите проверить, что лицо совпадает с предыдущими

**Как использовать:**
```bash
cd ~/voyage-narrative-engine
python3 scripts/python/check_consistency.py KIRA_MODULE_v14 /path/to/new_image.png /path/to/reference_image.png
```

**Без reference_image:**
```bash
python3 scripts/python/check_consistency.py KIRA_MODULE_v14 /path/to/new_image.png
# Скрипт найдёт последнюю успешную reference из generation_history
```

**Вывод:**
```
[INFO] Reference image: assets/images/character_sessions/kira/session_2026-06-05.png
[INFO] New image:       /path/to/new_image.png

Anatomic Anchor (check these features on BOTH images):
  [Face Shape  ] oval with slightly angular jawline, high cheekbones
  [Eyes        ] almond, slightly upturned outer corners, expressive brown with warm amber undertones
  ...

Manual Check Steps:
  1. Open both images side by side
  2. Compare face shape, eye shape/color, nose, lips, jaw
  3. Check distinguishing features (moles, scars, asymmetries)
```

**Результат:**
- `[pass]` — лицо консистентно, обновите `generation_history`
- `[fail]` — лицо другое, усильте `anatomic_anchor` в промпте

---

## 11. Обновление скрипта

Если вышла новая версия `session_finalize.py`:

```bash
cd ~/voyage-narrative-engine
git pull origin main
# Или перекачайте файл вручную
```

---

## 12. Полезные команды Termux

```bash
# Копировать файл
mv ~/storage/downloads/session.log sessions/raw/

# Просмотр большого файла
less sessions/stories/STORY_2026-06-08.md

# Поиск в файлах
grep -r "Кира" sessions/stories/

# Размер папки
du -sh sessions/

# Очистка временных файлов
rm -rf ~/.voyage_tmp
```

---

*Готово к использованию. Если что-то не работает — пришлите вывод команды с ошибкой.*
