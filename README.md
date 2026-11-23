# One More Unlock

Личный трекер достижений Steam. Список игр есть в общем индексе.

- [Общий индекс для ChatGPT](https://raw.githubusercontent.com/Kelebr1an/one-more-unlock/main/data/index.json) показывает прогресс, дату обновления и ссылку на достижения каждой игры.
- [Ручное обновление в GitHub Actions](https://github.com/Kelebr1an/one-more-unlock/actions/workflows/update-achievements.yml). Нажми **Run workflow**, выбери игру или `all` и дождись завершения.
- [Дневник прогресса](https://raw.githubusercontent.com/Kelebr1an/one-more-unlock/main/data/journal.json) хранит первый снимок каждой новой игры и изменения после обновлений. Уже полученные достижения первого снимка не считаются новыми.

По `fetched_at` проверяй свежесть данных. `last_progress` показывает последнее изменение прогресса и может относиться к более раннему обновлению.

[Прямая ссылка на список достижений RoR2](https://raw.githubusercontent.com/Kelebr1an/one-more-unlock/main/data/achievements.json).
