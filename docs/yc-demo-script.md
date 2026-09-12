# TETA+PI — YC Demo Video Script (~60–75 сек)

Формат: screen recording (без тебе в кадрі, лише голос за кадром) + курсор по
живому app.tetapi.dev. YC приймає посилання на unlisted YouTube відео.

**ВАЖЛИВО перед записом:** жодна з 5 існуючих прод-сутностей (`bob`,
`tetakta`, `shosho`, `Test Reporter`, `HELLFIRE Solutions`) не готова для
показу — усі позначені `UNVERIFIED` і мають тестовий сміттєвий контент
("premeum japan kichen" тощо). Перед записом:
1. Створи ОДНУ чисту тестову сутність з нормальною назвою/описом
   (не "test", не щось із назвою іншого твого проєкту).
2. Проведи її через реальну верифікацію (email або domain — найшвидше) так,
   щоб у кадрі бейдж змінився з `UNVERIFIED` на `VERIFIED` — це найсильніший
   момент відео.

---

## Сцена 1 — Проблема (0:00–0:12)
**Показати:** нічого з продукту ще — чорний екран або просто твій голос.

**Голос:**
> "AI agents are starting to act on our behalf — buying, negotiating, recommending.
> But there's no way for an agent to know if a business, a person, or another
> agent is who they claim to be. Right now, trust on the internet is built for
> humans reading a webpage — not for agents making decisions in milliseconds."

## Сцена 2 — Рішення, homepage (0:12–0:20)
**Показати:** `app.tetapi.dev` homepage — лого Θ+π, заголовок, search bar,
рядок `registry:attested · c2pa:verified · btc:ts:confirmed`.

**Голос:**
> "TETA+PI is trust infrastructure for the agent economy. We verify businesses,
> journalists, artists, and AI agents against official registries and
> cryptographic proof — and we make that verification queryable by AI agents
> directly, not just readable by humans."

## Сцена 3 — Claim flow (0:20–0:35)
**Показати:** клік "Create account" → `/claim` сторінка ("Claim your verified
identity") → вибір "Business/Organization" → sub-kind picker → Continue.
Швидко пройти форму (ім'я, опис) — прискорений запис (speed up 2-3x у монтажі).

**Голос:**
> "Claiming a page takes under a minute — no registry required to start.
> You add proof whenever you're ready: business email, domain ownership,
> official registry match, or C2PA-signed media from our Pi Camera hardware."

## Сцена 4 — Верифікація наживо (0:35–0:48)
**Показати:** на профілі — компактне іконічне меню верифікаторів (3.13),
клік на Email або Domain, проходження перевірки, **бейдж змінюється на
"✓ Verified"**.

**Голос:**
> "Once verified, the status is permanent and tamper-evident — every
> verification event is logged to an append-only audit trail on our backend."

## Сцена 5 — Публічна сторінка + AI-доступність (0:48–1:00)
**Показати:** `/e/[slug]` публічна сторінка з `✓ Verified` бейджем і блоками
контенту; потім рядок внизу сторінки "Verifiable by AI agents via MCP ·
mcp.tetapi.dev · teta_verify_entity" — виділити курсором.

**Голос:**
> "And this isn't just a badge for humans. Any AI agent — through our MCP
> server — can call `teta_verify_entity` and get a structured, machine-readable
> trust proof in one request. No scraping, no guessing, no hallucinated
> business names."

## Сцена 6 — Заклик (1:00–1:10)
**Показати:** назад на homepage, search bar із прикладом запиту.

**Голос:**
> "We're building the trust layer the agent economy doesn't have yet —
> and we're building it in public, live at tetapi.dev."

---

## Нотатки для монтажу
- Курсор рухай повільно й цілеспрямовано — не блукай по екрану.
- Прибери жовтий банер "under construction" з кадру, якщо можеш (він чесний,
  але відволікає в 60-секундному demo) — або залиш, якщо хочеш підкреслити
  "ship daily" темп розробки, YC це цінує.
  ("banner-h" — CSS-змінна, банер сам ховається лише через код, не силою).
- Якщо є доступ до Pi CAM (14.5 в роботі) — окрема коротша версія відео (30 сек)
  можна зробити тільки з фокусом на camera→C2PA→proof loop, це унікальна
  частина, якої немає в конкурентів.
- Швидкість: YC радить пряму мову, без пауз, без "um". Один дубль голосу
  поверх наперед змонтованого скрін-запису простіше, ніж запис одночасно.
