# Character Companion Product Roadmap V1

## 1. Purpose

Каноническая продуктовая дорожная карта Character Companion: завершённая основа, следующие срезы и обязательные границы. TASK_ID: `CHARACTER_COMPANION_PRODUCT_ROADMAP_V1`; дата: 2026-09-10; baseline: `feature/crp-mvp-v1`, `29aba88daccd16195bb62ad06caa2eaa91dbbe1b`.

Статусы срезов: `COMPLETE`, `IN_PROGRESS`, `PLANNED`, `DEFERRED`. `COMPLETE` относится к указанному объёму основы, а не ко всем будущим возможностям продукта. Основания — локальная история репозитория, связанные документы и явно указанное подтверждение владельца. Эта задача только документирует направление; она не разрешает реализацию, изменение данных или live acceptance.

## 2. Product Vision

Character Companion должен стать продуктом постоянного персонажа, выходящим за рамки generic chatbot. В центре — character identity, память, отношения, психология, narrative interaction, visual generation и discovery.

Целевой персонаж:

- остаётся узнаваемо собой и помнит релевантную историю;
- развивает отношения и поддерживает содержательный повседневный разговор;
- участвует в narrative/roleplay-сценах, сохраняя свою идентичность;
- имеет визуальное и медийное присутствие;
- доступен через масштабируемый каталог персонажей.

Романтическое взаимодействие может быть частью опыта; основное позиционирование продукта — постоянный персонаж с собственной идентичностью, а не эротический чатбот.

## 3. Architectural Boundaries

| Layer | Responsibility |
|---|---|
| CRP | Создаёт/реконструирует персонажа. |
| Accepted Character Package / Character Core | Источник истины об идентичности персонажа для runtime. |
| Runtime | Позволяет персонажу жить и взаимодействовать. |
| Memory | История взаимодействий и консолидированные воспоминания. |
| Relationship/Psych State | Изменяющееся состояние отношений и психологии в runtime. |
| CharacterLocalSnapshot | Принадлежащая Companion версионированная визуальная идентичность. |
| CharacterPublicProfile | Курируемый редакционный слой публичного представления пользователю. |
| Character Discovery | Поиск, индексирование и ранжирование курируемых публичных/searchable метаданных. |
| Admin Studio | Будущая поверхность авторинга и редактирования через явные границы. |

Эти слои нельзя сводить к одной модели данных. Controlled import отделяет Character Canon от Companion: Canon ID и Companion ID сопоставляются явно; после импорта Canon не является live runtime dependency. Визуальная генерация использует локальные snapshots Companion.

## 4. Current Foundation

| Product foundation | Status | Repository / project evidence |
|---|---|---|
| KIRA Companion MVP | COMPLETE | `500257c` — Companion app MVP. |
| Local LLM Provider foundation | COMPLETE | `a8c6225` — Local LLM Provider V1. |
| Product UX Requirements | COMPLETE | `7d14be6`; [requirements](CHARACTER_COMPANION_PRODUCT_UX_REQUIREMENTS_V1.md). |
| Cinematic First Release UX | COMPLETE | `14d0ed8` — cinematic first-release UX. |
| Secure Desktop Foundations | COMPLETE | `a5aba74` — secure desktop foundations. |
| KIRA Release Assembly / portrait binding | COMPLETE | `e8bc8df` — assembly; `2498bed` — approved portrait binding. |
| Focus / Local User Profile / i18n | COMPLETE | `65e124c`; [Focus / identity / i18n](FOCUS_MODE_USER_IDENTITY_I18N_UX_V2.md). |
| Media Provider Roles / Model Roles | COMPLETE | `c230a3b`; [configuration contract](MEDIA_PROVIDERS_AND_MODEL_ROLES_V1.md). |
| Chat Controls + Writing Assistant | COMPLETE | `8f008b5`; [chat controls](CHAT_CONTROL_AND_COMPOSER_ASSISTANT_V1.md), с уточнением linear-history решения ниже. |
| Runtime / Consolidated Memory foundations | COMPLETE | `9174f8f`, `0787e1b`, `db2a88c`, `aa79ee9` — persistent memory, consolidation, relations, operator UI. |
| Relationship / Psychology state foundations | COMPLETE | `22cbbea` — relationship and psychology evolution. |
| Controlled Character Canon → Companion Local Snapshot import | COMPLETE | `2d96321`; [visual pipeline provenance](VISUAL_PIPELINE_VENDOR_PROVENANCE_V1.md), Slice A. |
| Explicit Canon ID / Companion ID mapping | COMPLETE | `31e094ed00ea78078d182a8a7a3f477618c49a2c`. |
| Real KIRA local visual snapshot v1 | COMPLETE | Подтверждение владельца в исходном задании этой roadmap; локальные пользовательские данные в этой задаче не инспектировались. |
| Reference Selection + VisualContext + VisualPromptPackage | COMPLETE | `2f15559ceeace4907d69c67b3ffb182319306153`; provenance, Slice B. |
| IMAGE_GENERATION Provider Adapter + ImageJobService backend integration | COMPLETE | `0528035a3a86a900a91e0cbeca68bd2c7055e8c0`; provenance, Slice C. |

Backend image pipeline завершён в границах интеграции. Release default остаётся `UnavailableImageGenerator`; реальная генерация в Companion UX ещё не включена. Model-role configuration сама по себе не означает доступность всех media capabilities.

Исторические уточнения: [RC1 assembly](RELEASE_CANDIDATE_RC1.md) описывает портрет до последующего binding-коммита `2498bed`. [CONFLICT] Старый next-slice contract `RECENT_TAIL_EDIT_SUPERSESSION_V1` в Chat Controls противоречит текущему решению владельца. Для этой roadmap действует твёрдое решение из раздела 10: sent-message edit/supersession/branching намеренно оставлены вне дальнейшего развития. Исходные документы здесь не изменяются.

## 5. Completed Public Profile Foundation

`CHARACTER_PUBLIC_PROFILE_V1` — Status: `COMPLETE`.

Commit: `29aba88daccd16195bb62ad06caa2eaa91dbbe1b`. Основание: [Character Public Profile V1](CHARACTER_PUBLIC_PROFILE_V1.md), карточки `CharacterList`, `CharacterProfileDrawer` и профильный backend этого коммита.

Реализованная основа:

- карточки персонажей в sidebar: avatar/photo, display name, short description, выбор персонажа и «Подробнее»;
- правый profile drawer с затемнением и blur фона;
- long description и необязательные упорядоченные profile sections;
- курируемые image/video media как основа публичного профиля;
- структура card/profile для N персонажей и будущего редактирования через Admin Studio.

`CharacterPublicProfile` — editorial/public presentation data. Его редактирование не должно автоматически изменять Accepted Character Package, runtime personality, Memory, Relationship/Psych State, CharacterLocalSnapshot или CRP evidence/claims. Готовность структуры для N персонажей не означает уже выпущенный масштабируемый каталог.

Для KIRA всё ещё требуется одобренный владельцем публичный редакционный текст. Примечание по контенту: `OWNER_PUBLIC_COPY_REQUIRED` — это не дополнительный статус среза. Функция остаётся `COMPLETE`; подготовка и публикация реального KIRA public copy — отдельная content task. Внутренние CRP-данные не подменяют публичный текст.

## 6. Planned Product Slices

### IMAGE_GENERATION_PRODUCT_WIRING_V1 — Slice D

Status: `PLANNED`. Подключить завершённый backend image pipeline к реальному Companion UX:

- «Создать изображение...» и «Кадр по контексту»;
- provider/model readiness UX;
- состояния прогресса и ошибки;
- интеграция результата ImageJob в Gallery, Background и Cover.

Зависимости: local snapshot, visual context/prompt pipeline, image adapter/job backend, provider/model roles. Real provider/cloud acceptance остаётся отдельным шагом с явным разрешением; эта roadmap не включает live generation.

### CHAT_MESSAGE_FEEDBACK_AND_CONTINUE_V1

Status: `PLANNED`. Добавить 👍 / 👎, необязательные причины и свободный текст feedback, а также «Продолжить» под последним ответом персонажа.

Причинное правило: **«Продолжить» → NEW CHARACTER_MESSAGE**. Это новый ответ персонажа в конце линейной истории; предыдущий ответ не редактируется, не регенерируется и не supersede-ится.

Feedback — данные оценки и продуктового обучения. Он не переписывает напрямую Character Package, факты Memory, personality или Relationship/Psych State. Возможные применения: предпочтения пользователя по стилю ответа, аналитика качества, behavioral evaluation dataset, контролируемые будущие улучшения и Evolution proposals, одобренные человеком.

### Остальные срезы

| Slice | Status | Product outcome |
|---|---|---|
| CHARACTER_NARRATIVE_INTERACTION_V1 | PLANNED | Полноценное narrative/roleplay-взаимодействие с сохранением идентичности; раздел 7. |
| CHARACTER_NARRATIVE_BEHAVIORAL_VALIDATION_V1 | PLANNED | Сценарная оценка поведения и непрерывности сцен; раздел 7. |
| CHARACTER_DISCOVERY_V1 | PLANNED | Поиск и навигация в области «Персонажи»; раздел 8. |
| CHARACTER_DISCOVERY_SEMANTIC_V1 | PLANNED | Интерпретация свободного запроса поверх контролируемого поиска; раздел 8. |
| CHARACTER_ADMIN_STUDIO_V1 | PLANNED | Авторинг, публикация и управление персонажами через явные границы; раздел 9. |

## 7. Narrative / Roleplay Direction

`CHARACTER_NARRATIVE_INTERACTION_V1` — существенная продуктовая возможность, а не простая правка prompt. Концептуальные режимы: `CHAT`, `ROLEPLAY`, `STORY`; окончательные UI labels пока не фиксируются.

Будущая концептуальная цепочка:

```text
Character Package + Memory + Relationship/Psych State + Scene State
    → Narrative Controller
    → Character generation
```

Целевые возможности: scene continuity; речь, действия и narration; инициатива персонажа; continuation; context-aware storytelling; стиль ответа с учётом режима; сохранение идентичности между обычным чатом и roleplay. Более богатые романтические и интимные истории возможны там, где это допускают модель, провайдер и политика продукта. Отдельная «сексуальная версия» персонажа не создаётся: авторитетной остаётся та же идентичность.

**Narrative Controller — будущий концептуальный слой, Status: `PLANNED`.** До окончательной формулировки он определяет тип следующего сценического хода: ответить, спросить, приблизиться/отдалиться, сменить тему, начать действие, продолжить незавершённое действие, вспомнить релевантное событие или продвинуть сцену. Решение зависит от конкретной личности персонажа, отношений, памяти и текущей сцены. Реализация контроллера здесь не утверждается.

**Scene State — будущая концепция, Status: `PLANNED`.** Возможное содержание: место, время, ситуация, настроение, участники, недавнее событие/действие, незавершённое действие, межличностная дистанция/контекст. Это не новая схема и не переопределение текущего `CompanionScene`.

`CHARACTER_NARRATIVE_BEHAVIORAL_VALIDATION_V1` — Status: `PLANNED`. Семейства будущих сценариев: обычное взаимодействие, разногласие, примирение, ревность, юмор, уязвимость, романтика, эмоциональное напряжение, разрешённые intimate/adult-сцены, совместные события и путешествия.

Вопросы оценки:

- остаётся ли персонаж собой;
- корректно ли используется релевантная память и отражаются отношения;
- соответствует ли инициатива характеру;
- сохраняется ли непрерывность сцены;
- не становится ли narration повторяющимся или шаблонным;
- не деградирует ли персонаж до generic roleplay bot.

Будущие roleplay/media-возможности зависят от выбранных provider/model и их текущих возможностей и политик. Нельзя считать, что все провайдеры одинаково поддерживают или разрешают романтическое/adult-поведение. Исследование актуальных capabilities/policies — отдельная задача; здесь такие сведения не проверяются и не предполагаются. Существующие safety-механизмы сохраняются.

## 8. Character Discovery Direction

`CHARACTER_DISCOVERY_V1` — Status: `PLANNED`. Основная продуктовая область — «Персонажи». Существующие карточки уже дают основу: avatar, display name, short description, selection, «Подробнее». Далее добавляются text search, filters, tags/facets, sorting, favorites/recent там, где это уместно. Детальная реализация и схема индекса пока не фиксируются.

`CHARACTER_DISCOVERY_SEMANTIC_V1` — Status: `PLANNED`. Пример запроса: «Хочу умного, немного ироничного персонажа, который любит путешествия и не слишком разговорчив».

Предпочтительная будущая цепочка:

```text
Свободный запрос → semantic/AI interpretation → structured requirements
    → deterministic filters → semantic ranking → optional AI explanation
```

Одна LLM не должна единолично определять истину поиска. Индекс и поиск используют только курируемые публичные/searchable метаданные. В индекс не попадают raw CRP evidence, hidden claims, system prompts, private Memory, credentials или hidden runtime state.

## 9. Admin Studio Direction

`CHARACTER_ADMIN_STUDIO_V1` — Status: `PLANNED`. Будущая область владения: display name, short/long description, profile sections, profile media, primary image, visibility/order, searchable tags/facets и, где уместно, контролируемые операции import/update/version персонажа.

```text
Admin Studio → authored/published CharacterPublicProfile
    → Companion cards/detail drawer → Character Discovery index/search
```

Studio редактирует authoring/public metadata через явные границы. Оно не должно незаметно переписывать runtime personality или историческую память; controlled character import/update/version — отдельные явные операции, не побочный эффект редактирования профиля.

**PUBLIC PROFILE MEDIA != SESSION / CHAT GALLERY MEDIA.** Публичные медиа курирует автор/admin; session gallery содержит медиа, созданные при взаимодействии пользователя. Приватные/session images не публикуются автоматически в профиле. Будущее Admin Studio может явно продвигать выбранные медиа в публичный профиль.

## 10. Product Invariants

1. Character identity и public presentation — отдельные слои.
2. Редактирование public profile не меняет незаметно runtime personality.
3. Memory/runtime evolution никогда не переписывает Character Package незаметно.
4. Character Canon не является live runtime dependency после controlled import.
5. Visual generation использует принадлежащие Companion local snapshots.
6. Public profile media != private/session gallery media; автоматической публикации нет.
7. Feedback не переобучает и не переписывает персонажа напрямую, включая Memory facts и Relationship/Psych State.
8. **Твёрдое решение (FIRM): после Send история неизменяема, линейна и append-only.** Sent-message edit/supersession/branching намеренно отвергнуты и не возвращаются в roadmap. Исправления — новые сообщения. Presentation hide не стирает причинную историю персонажа. «Продолжить» добавляет новый ответ персонажа.
9. Narrative/roleplay сохраняет идентичность персонажа во всех режимах.
10. Discovery использует курируемые/searchable profile data, а не скрытые данные реконструкции, приватную память или runtime state.
11. Provider capabilities/policies проверяются, а не предполагаются.

## 11. Recommended Execution Order

`CHARACTER_PUBLIC_PROFILE_V1` уже `COMPLETE` и предшествует следующим работам:

1. `IMAGE_GENERATION_PRODUCT_WIRING_V1`.
2. `CHAT_MESSAGE_FEEDBACK_AND_CONTINUE_V1`.
3. `CHARACTER_NARRATIVE_INTERACTION_V1`.
4. `CHARACTER_NARRATIVE_BEHAVIORAL_VALIDATION_V1`.
5. `CHARACTER_DISCOVERY_V1`.
6. `CHARACTER_DISCOVERY_SEMANTIC_V1`.
7. `CHARACTER_ADMIN_STUDIO_V1`.

Порядок рекомендательный, не необратимый. Admin Studio может перейти раньше, если масштабируемый авторинг или управление новыми персонажами станет блокером. Публикация KIRA public copy остаётся отдельной content task; real provider/cloud acceptance требует отдельного явного разрешения.

## 12. Status Table

| Area | Slice | Status | Dependency | Notes |
|---|---|---|---|---|
| Companion | KIRA MVP + Local LLM Provider | COMPLETE | Character Core / Runtime | Основания в разделе 4. |
| UX / Desktop | Product UX, Cinematic UX, Secure Desktop, Release Assembly / portrait, Focus / Local User Profile / i18n | COMPLETE | Companion MVP | Завершённый ограниченный foundation scope. |
| Controls / Models | Media Provider Roles / Model Roles, Chat Controls + Writing Assistant | COMPLETE | Companion / settings | Не означает live media activation. |
| Runtime | Runtime / Consolidated Memory, Relationship / Psychology foundations | COMPLETE | Accepted Character Package | Изменяемое состояние отделено от identity truth. |
| Visual identity | Controlled import + ID mapping + KIRA local snapshot v1 | COMPLETE | Controlled Canon import | Snapshot v1 подтверждён владельцем; Canon не live dependency. |
| Visual backend | Reference Selection / VisualContext / VisualPromptPackage + IMAGE_GENERATION adapter / ImageJobService | COMPLETE | Local snapshot / model roles | Slices B/C; product wiring впереди. |
| Public profile | CHARACTER_PUBLIC_PROFILE_V1 | COMPLETE | Companion cards / profile store | `29aba88daccd16195bb62ad06caa2eaa91dbbe1b`; `OWNER_PUBLIC_COPY_REQUIRED` — отдельный контент. |
| Images | IMAGE_GENERATION_PRODUCT_WIRING_V1 | PLANNED | Visual backend + local snapshot + model readiness | Slice D; Gallery / Background / Cover; live acceptance отдельно. |
| Chat | CHAT_MESSAGE_FEEDBACK_AND_CONTINUE_V1 | PLANNED | Linear history / Chat Controls | Feedback — evaluation data; Continue → NEW CHARACTER_MESSAGE. |
| Narrative | CHARACTER_NARRATIVE_INTERACTION_V1 | PLANNED | Identity + Memory + Relationship/Psych State | Концепции Scene State / Narrative Controller; не prompt-only tweak. |
| Evaluation | CHARACTER_NARRATIVE_BEHAVIORAL_VALIDATION_V1 | PLANNED | Narrative interaction | Сценарии и вопросы оценки в разделе 7. |
| Catalog | CHARACTER_DISCOVERY_V1 | PLANNED | PublicProfile / curated searchable metadata | Область «Персонажи». |
| Semantic search | CHARACTER_DISCOVERY_SEMANTIC_V1 | PLANNED | Discovery filters/index + curated metadata | AI interpretation + deterministic filters + semantic ranking. |
| Authoring | CHARACTER_ADMIN_STUDIO_V1 | PLANNED | PublicProfile contract / explicit authoring boundaries | Может идти раньше при блокере масштабирования. |
