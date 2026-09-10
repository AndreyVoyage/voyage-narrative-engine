/**
 * Russian UI dictionary — the reference locale. Every other locale's key set is
 * type-checked against `keyof typeof ru`. Values here are the exact strings the
 * app shipped with before i18n, so the Russian UI is visually unchanged.
 *
 * These are APPLICATION-CHROME strings only. Conversation text, character
 * replies, Scene content and provider output are NEVER passed through here.
 */

export const ru = {
  // -- app shell -----------------------------------------------------------
  "app.brandFallback": "Companion · Cinematic",
  "app.loading": "Загрузка…",
  "app.imageWorking": "Изображение создаётся…",
  "app.settings": "Настройки",
  "app.providerNeedsConfig": "Провайдер диалога не настроен — открыть Настройки",
  "app.describeImage": "Опишите изображение",

  // -- navigation / lists ------------------------------------------------
  "nav.characters": "Персонажи",
  "nav.dialogues": "Диалоги",
  "characters.empty": "Нет доступных персонажей.",
  "dialogues.new": "Новый диалог",
  "dialogues.empty": "Диалогов пока нет.",
  "dialogues.noResults": "Ничего не найдено.",
  "dialogues.search": "Поиск по диалогам",
  "dialogues.previewEmpty": "Новый диалог",

  // -- conversation ----------------------------------------------------
  "conversation.choosePrompt": "Выберите или создайте диалог.",
  "conversation.empty": "Сообщений пока нет.",
  "conversation.you": "Вы",
  "conversation.character": "Персонаж",
  "conversation.focusMode": "Фокус-режим",
  "conversation.retry": "Повторить",

  // -- image jobs ----------------------------------------------------
  "job.queued": "Изображение поставлено в очередь",
  "job.generating": "Создаём изображение…",
  "job.ready": "Изображение готово",
  "job.failed": "Не удалось создать изображение",

  // -- composer ----------------------------------------------------
  "composer.placeholder": "Написать сообщение…",
  "composer.send": "Отправить",
  "composer.sending": "…",
  "composer.menuCreate": "Создать",
  "composer.menuAttach": "Прикрепить",
  "composer.createImage": "Создать изображение…",
  "composer.contextFrame": "Кадр по контексту",
  "composer.attachImage": "Изображение · Скоро",
  "composer.attachDocument": "Документ · Скоро",
  "composer.attachAudio": "Аудио · Скоро",
  "composer.attachVideo": "Видео · Скоро",
  "composer.attachSoonTitle": "Скоро — нужен модуль безопасной загрузки файлов",
  "composer.recordVoice": "Записать голосовое сообщение · Скоро",

  // -- new dialog ----------------------------------------------------
  "newDialog.title": "Новый диалог",
  "newDialog.modeOrdinary": "Обычный разговор",
  "newDialog.modeScene": "Начать со сцены",
  "newDialog.name": "Название (необязательно)",
  "newDialog.scene": "Сцена",
  "newDialog.randomScenario": "🎲 Случайный сценарий",
  "newDialog.describe": "Опишите обстоятельства",
  "newDialog.cancel": "Отмена",
  "newDialog.start": "Начать",

  // -- scene fields ----------------------------------------------------
  "scene.place": "Место",
  "scene.time": "Время",
  "scene.situation": "Ситуация",
  "scene.mood": "Настроение",
  "scene.notSet": "Не задано",
  "scene.ordinaryConversation": "Обычный разговор",

  // -- right wing ----------------------------------------------------
  "wing.header": "Персонаж и сцена",
  "wing.createImage": "Создать изображение…",
  "wing.contextFrame": "Кадр по контексту",
  "wing.makeCover": "Сделать обложкой диалога",
  "wing.currentCover": "Текущая обложка",
  "wing.sceneImageAlt": "Изображение сцены",
  "wing.gallery": "Галерея",

  // -- focus mode ----------------------------------------------------
  "focus.exit": "Выйти (Esc)",
  "focus.layoutGroup": "Режим фокуса",
  "focus.layout.background": "Фон",
  "focus.layout.side_gallery": "Галерея сбоку",
  "focus.layout.chat_only": "Только чат",
  "focus.cycle": "Сменить вид",
  "focus.newMessages": "↓ Новые сообщения",
  "focus.gallery.prev": "Предыдущее",
  "focus.gallery.next": "Следующее",
  "focus.gallery.counter": "{index} / {total}",
  "focus.gallery.makeCover": "Сделать обложкой",
  "focus.gallery.makeBackground": "Сделать фоном",
  "focus.gallery.clearBackground": "Обычный фон",
  "focus.gallery.portrait": "Портрет",
  "focus.gallery.cover": "Обложка",
  "focus.gallery.frame": "Кадр",
  "focus.portraitAlt": "Портрет: {name}",

  // -- local user profile ----------------------------------------------
  "profile.section": "Профиль",
  "profile.displayName": "Отображаемое имя",
  "profile.displayNameHint": "Так вас будет видно в диалоге. Хранится только на этом устройстве.",
  "profile.defaultName": "Пользователь",
  "profile.avatar": "Фото профиля",
  "profile.avatarComingSoon": "Фото профиля — скоро",
  "profile.language": "Язык интерфейса",

  // -- character public profile (cards + detail drawer) ---------------
  "profile.details": "Подробнее",
  "profile.close": "Закрыть",
  "profile.dialogAria": "Профиль персонажа",
  "profile.aboutFallback": "Подробное описание появится позже.",
  "profile.mediaTitle": "Фото и видео",
  "profile.mediaEmpty": "Медиа пока нет.",
  "profile.playVideo": "Воспроизвести видео",

  // -- settings ----------------------------------------------------
  "settings.title": "Настройки",
  "settings.close": "Закрыть",
  "settings.section.providers": "Провайдеры",
  "settings.section.roles": "Роли моделей",
  "settings.section.local": "Локальная модель",
  "settings.section.security": "Безопасность",
  "settings.rolesHint": "В этом релизе используется роль DIALOGUE. Остальные роли — задел на будущее.",
  "settings.dialogueProvider": "DIALOGUE — провайдер",
  "settings.dialogueModel": "DIALOGUE — модель",
  "settings.localBaseUrl": "Базовый URL",
  "settings.localNumCtx": "Размер контекста (num_ctx)",
  "settings.testConnection": "Проверить соединение",
  "settings.connect": "Подключить",
  "settings.replace": "Заменить",
  "settings.deleteKey": "Удалить ключ",
  "settings.keyPlaceholder": "Ключ API",
  "settings.keyReplacePlaceholder": "Заменить ключ API",
  "settings.status.ready": "Готов",
  "settings.status.connected": "Подключено",
  "settings.status.disconnected": "Не подключено",
  "settings.providerModel": "Модель: {model}",
  "settings.providerRoles": "Роли: {roles}",
  "settings.providerKey": "Ключ: {tail}",
  "settings.security.keys": "Ключи API хранятся в защищённом хранилище ОС и не попадают в интерфейс, историю или логи.",
  "settings.security.fallback": "Автоматический переход на облачного провайдера при сбое:",
  "settings.security.fallbackOn": "включён",
  "settings.security.fallbackOff": "выключен",
  "settings.security.fallbackDefault": "по умолчанию выключен",
  "settings.security.upload": "Загрузка произвольных файлов недоступна: модуль безопасной обработки вложений ещё не подключён.",
  "settings.contextWarn": "Размер контекста меньше рекомендуемого ({hint}); ответ KIRA может обрезаться.",

  // -- model roles (media configuration foundation) -------------------
  "settings.section.modelRoles": "Модели по задачам",
  "settings.modelRolesHint": "Ключ доступа привязан к провайдеру, а не к роли: один ключ работает для всех задач этого провайдера.",
  "settings.modelChangeNote": "Доступность моделей зависит от провайдера и может меняться.",
  "settings.roleProvider": "Провайдер",
  "settings.roleModel": "Модель",
  "settings.roleNoProvider": "Нет доступного провайдера",
  "settings.runtimeWiredBadge": "Активно в рантайме",
  "settings.modelUnverified": "не проверено",
  "role.DIALOGUE": "Диалог",
  "role.VISION": "Анализ изображений",
  "role.IMAGE_GENERATION": "Генерация изображений",
  "role.VIDEO_GENERATION": "Генерация видео",
  "role.STT": "Распознавание речи",
  "role.TTS": "Голос персонажа",
  "role.REALTIME": "Звонки / Realtime",
  "role.WRITING_ASSISTANT": "Помощник написания",
  "role.LOCAL_ALTERNATIVE": "Локальная модель",
  "readiness.READY": "Готово",
  "readiness.CONFIGURED_CREDENTIAL_MISSING": "Настроено — нужен ключ",
  "readiness.NOT_CONFIGURED": "Не настроено",
  "readiness.UNSUPPORTED": "Не поддерживается",
  "readiness.FUTURE_NOT_WIRED": "Подключение будет выполнено на следующем этапе",

  // -- error codes (mapped from stable backend codes) ------------------
  // -- composer writing assistant + message/chat controls ------------
  "assistant.rewrite": "Помощник написания",
  "assistant.working": "Помощник пишет…",
  "assistant.restoreOriginal": "Вернуть исходный текст",
  "assistant.unavailable": "Настройте модель «Помощник написания» в настройках.",
  "assistant.failed": "Не удалось получить подсказку. Черновик сохранён.",
  "message.actions": "Действия с сообщением",
  "message.copy": "Копировать",
  "message.copied": "Скопировано",
  "message.hide": "Скрыть сообщение",
  "message.unhide": "Показать сообщение",
  "message.showHidden": "Показать скрытые ({count})",
  "message.hideHidden": "Скрыть скрытые",
  "chat.actions": "Действия с диалогом",
  "chat.rename": "Переименовать",
  "chat.renamePlaceholder": "Название диалога",
  "chat.renameSave": "Сохранить",
  "chat.hide": "Скрыть диалог",
  "chat.restore": "Восстановить",
  "chat.hiddenSection": "Скрытые ({count})",

  "error.assistant_not_configured": "Настройте модель «Помощник написания» в настройках.",
  "error.assistant_failed": "Не удалось получить подсказку. Попробуйте ещё раз.",
  "error.provider_not_configured": "Провайдер диалога не настроен. Откройте Настройки и выберите локальную модель или облачного провайдера.",
  "error.missing_credential": "Не задан ключ доступа для выбранного провайдера. Добавьте ключ в Настройках.",
  "error.provider_failed": "Провайдер не смог обработать запрос. Попробуйте ещё раз позже.",
  "error.provider_unavailable": "Провайдер сейчас недоступен. Проверьте подключение и настройки.",
  "error.generator_unavailable": "Генератор изображений недоступен в этой сборке.",
  "error.backend_unavailable": "Нет подключения к серверу.",
  "error.empty_message": "Сообщение не может быть пустым.",
  "error.unknown": "Что-то пошло не так. Попробуйте ещё раз.",
} as const;

export type TranslationKey = keyof typeof ru;
