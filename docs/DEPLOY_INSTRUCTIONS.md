# Инструкция: Загрузка ролей в репозиторий (без ошибок)

## ⚠️ Что пошло не так в прошлый раз (анализ истории)

| Ошибка | Причина | Как исправлено |
|--------|---------|----------------|
| `deploy_from_archive.sh: No such file or directory` | Скрипт искали в текущей папке, а не в репозитории | Скрипт теперь ищет архив в 3 местах: `~/`, `~/voyage-narrative-engine/`, `./` |
| `mkdir: cannot create directory '/tmp': Read-only file system` | Использовали `/tmp` на Android | Теперь используем `$HOME/.voyage_tmp` |
| `git pull` → конфликты | Пуллили без проверки изменений | Теперь нет `git pull` в скрипте — только `git add` + `git commit` |
| Архив распаковывался вне репозитория | Не проверяли `pwd` | Скрипт явно переходит в `$HOME/voyage-narrative-engine` |
| Файлы не попадали в git | Забывали `git add` | Скрипт делает `git add` автоматически |

---

## 📦 Что в архиве

```
voyage_roles_update_2026-06-08.zip
├── roles/
│   ├── ROLE_STATE_MANAGER_v1.0_PROMPT.md
│   ├── ROLE_NARRATIVE_EDITOR_v1.1_PROMPT.md
│   └── ROLE_VISUAL_EXTRACTOR_v1.0_PROMPT.md
├── docs/
│   ├── ANALYSIS_WORKFLOW_v1.0.md
│   └── SESSION_FINALIZATION_WORKFLOW_v1.1.md
└── scripts/termux/
    └── deploy_roles.sh
```

---

## 🚀 Способ 1: Автоматический (через скрипт)

### Шаг 1. Скачайте архив

Переместите файл `voyage_roles_update_2026-06-08.zip` в **домашнюю папку Termux** (`~/`).

Как это сделать:
- Через `scp` с компьютера
- Или скачайте через браузер Android в `Downloads/`, потом:
```bash
cp ~/storage/downloads/voyage_roles_update_2026-06-08.zip ~/
```

### Шаг 2. Запустите скрипт

```bash
cd ~
chmod +x voyage-narrative-engine/scripts/termux/deploy_roles.sh  # если архив уже распакован
# ИЛИ если архив просто лежит в ~/ :
unzip -o ~/voyage_roles_update_2026-06-08.zip -d ~/voyage_tmp_extract
cp ~/voyage_tmp_extract/scripts/termux/deploy_roles.sh ~/deploy_roles.sh
chmod +x ~/deploy_roles.sh
bash ~/deploy_roles.sh
```

**Или проще — вручную (Способ 2).**

---

## ✋ Способ 2: Ручной (надёжнее, рекомендуется)

### Шаг 1. Перейдите в репозиторий

```bash
cd ~/voyage-narrative-engine
pwd  # Должно вывести: /data/data/com.termux/files/home/voyage-narrative-engine
```

**Если папки нет:**
```bash
cd ~
git clone https://github.com/AndreyVoyage/voyage-narrative-engine.git
cd voyage-narrative-engine
```

### Шаг 2. Создайте папки (если ещё нет)

```bash
mkdir -p roles
mkdir -p docs
mkdir -p sessions/raw
mkdir -p sessions/state
mkdir -p sessions/memory
mkdir -p sessions/stories
mkdir -p sessions/visuals
mkdir -p scripts/termux
```

### Шаг 3. Распакуйте архив (временная папка в HOME, не /tmp!)

```bash
cd ~
mkdir -p .voyage_tmp
unzip -o voyage_roles_update_2026-06-08.zip -d .voyage_tmp
```

### Шаг 4. Скопируйте файлы

```bash
cp ~/.voyage_tmp/roles/*.md ~/voyage-narrative-engine/roles/
cp ~/.voyage_tmp/docs/*.md ~/voyage-narrative-engine/docs/
cp ~/.voyage_tmp/scripts/termux/*.sh ~/voyage-narrative-engine/scripts/termux/
chmod +x ~/voyage-narrative-engine/scripts/termux/*.sh
```

### Шаг 5. Проверьте

```bash
cd ~/voyage-narrative-engine
ls roles/
# Должно быть:
# ROLE_NARRATIVE_EDITOR_v1.1_PROMPT.md
# ROLE_STATE_MANAGER_v1.0_PROMPT.md
# ROLE_VISUAL_EXTRACTOR_v1.0_PROMPT.md

ls docs/
# Должно быть:
# ANALYSIS_WORKFLOW_v1.0.md
# SESSION_FINALIZATION_WORKFLOW_v1.1.md

ls sessions/
# Должно быть: raw/ state/ memory/ stories/ visuals/
```

### Шаг 6. Git-commit

```bash
cd ~/voyage-narrative-engine
git add roles/ docs/ sessions/ scripts/
git commit -m "roles: add State Manager, Narrative Editor v1.1, Visual Extractor

docs: add workflow analysis and session finalization guide
sessions: create folder structure for raw/state/memory/stories/visuals"
```

### Шаг 7. Push (если нужно)

```bash
git push origin main
```

Если выдаёт ошибку авторизации — проверьте `git remote -v` и настройте токен:
```bash
git remote set-url origin https://TOKEN@github.com/AndreyVoyage/voyage-narrative-engine.git
```

---

## 📁 Что должно получиться в репозитории

```
voyage-narrative-engine/
├── roles/                          # ← НОВОЕ
│   ├── ROLE_STATE_MANAGER_v1.0_PROMPT.md
│   ├── ROLE_NARRATIVE_EDITOR_v1.1_PROMPT.md
│   └── ROLE_VISUAL_EXTRACTOR_v1.0_PROMPT.md
├── docs/                           # ← НОВОЕ + обновлено
│   ├── ANALYSIS_WORKFLOW_v1.0.md
│   ├── SESSION_FINALIZATION_WORKFLOW_v1.1.md
│   └── ... (старые файлы)
├── sessions/                       # ← НОВАЯ СТРУКТУРА
│   ├── raw/
│   ├── state/
│   ├── memory/
│   ├── stories/
│   └── visuals/
├── scripts/termux/                 # ← НОВОЕ
│   └── deploy_roles.sh
├── personas/                       # (уже было)
├── scenarios/                      # (уже было)
├── state/                          # (уже было)
└── ...
```

---

## 🔍 Проверка после загрузки

Выполните в Termux:

```bash
cd ~/voyage-narrative-engine
echo "=== Роли ==="
ls -la roles/
echo "=== Доки ==="
ls -la docs/
echo "=== Сессии ==="
ls -la sessions/
echo "=== Git статус ==="
git status
```

Если `git status` показывает `nothing to commit, working tree clean` — всё загружено.

---

## 🆘 Если что-то пошло не так

**Проблема:** `unzip: command not found`
**Решение:**
```bash
pkg update && pkg install unzip -y
```

**Проблема:** `git: not found`
**Решение:**
```bash
pkg install git -y
```

**Проблема:** Архив не скачивается на телефон
**Решение:** Откройте архив в браузере телефона, скачайте, потом:
```bash
cp ~/storage/downloads/voyage_roles_update_2026-06-08.zip ~/
```

**Проблема:** Нет прав на запись в репозиторий
**Решение:** Проверьте, что вы владелец папки:
```bash
ls -la ~/ | grep voyage-narrative-engine
# Должно быть: drwxr-xr-x ... u0_aXXX u0_aXXX
```

---

## ✅ Чек-лист (галочки)

- [ ] Архив `voyage_roles_update_2026-06-08.zip` лежит в `~/`
- [ ] `cd ~/voyage-narrative-engine` работает без ошибок
- [ ] Папки `roles/`, `docs/`, `sessions/*/` созданы
- [ ] Файлы скопированы (`ls roles/` показывает 3 файла)
- [ ] `git add` выполнен
- [ ] `git commit` выполнен
- [ ] `git push` выполнен (опционально)

После этого можно использовать workflow: сессия → лог в `sessions/raw/` → обработка 3 ролями.
