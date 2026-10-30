# Пакет промптов для генерации настоящей анимации (image-to-video)

Если нужен не аниматик, а живая анимация — эти плейты из `images/` скармливаются
видеомодели (Kling 2.x / Runway Gen-4 / Veo 3 / Hailuo / Seedance) как **первый кадр**,
плюс промпт ниже. Сгенерированные клипы затем собираются моим пайплайном
(`src/render2.py` принимает внешние клипы вместо плейтов — см. «Как собрать»).

**Единый стилевой суффикс** (добавлять в конец каждого промпта):

> Hand-drawn 2D anime, MAPPA / Attack on Titan production style, cel-shaded characters on
> painted backgrounds, muted desaturated palette (concrete grey, dusty brown, cold night blue,
> dried blood red), heavy film grain, dust in the air, 24 fps, subtle line boil,
> limited animation with held frames — do NOT make it look like a 3D render or a still photo.

**Негатив:** photorealistic, 3d render, cgi, smooth interpolated motion, modern clean digital
look, bright saturated colours, text, watermark, subtitles.

---

## Ключевые кадры (20 клипов вместо 305)

| # | TC | Сек | Плейт | Промпт |
|---|---|---|---|---|
| 1 | 00:11 | 4 | `a4_cup` | Steam rises in slow curls from the paper cup; the thin hands tighten slightly; the cup trembles once. Camera inches in with a tiny handheld drift. |
| 2 | 00:19 | 4 | `a3_eyes` | The boy blinks once, slowly; his pupils drift to the side and settle. Hair strands move a few pixels in the wind. Camera pushes in 5%. |
| 3 | 00:49 | 5 | `a6_flash_child` | The child sprints through the rain, drops of water streaking past the lens; edges of the image smear like a damaged memory. Grain flickers, exposure pulses. |
| 4 | 01:16 | 5 | `a7_stand` | The boy stands up from the bench, his thin silhouette straightening; a gust of dust and loose paper sweeps across the empty street. Slow push-in. |
| 5 | 02:03 | 5 | `b2_strapped` | Overhead shot: the boy breathes out and his eyes close; the leather straps creak and tighten by a millimetre. Single bulb above flickers. |
| 6 | 02:38 | 6 | `b4_bulb` | The filament flares and dims rhythmically; dust motes swirl in the halo; the camera creeps toward the glow until the frame is pure white. |
| 7 | 03:28 | 7 | `c1_road_wide` | The chained caravan shuffles forward in slow, exhausted steps, chains swinging between ankles, dust glowing in the red moonlight. Long push-in from behind. |
| 8 | 03:38 | 5 | `c2_shackles` | POV: the shackled hands shake; breath vapour drifts through the frame; the chain links jingle as the arms tremble harder. |
| 9 | 04:12 | 6 | `c4_mountain` | A wide upward tilt along the black mountain; thin crimson light pulses inside the summit crack; dust falls from the peak. |
| 10 | 05:52 | 5 | `d1_panic` | Rocks and ice crash into the road, dust exploding outward; the silhouettes scatter and stumble. Handheld shake, one rock passes close to the lens. |
| 11 | 06:05 | 5 | `d2_king_reveal` | The enormous shape shifts its weight almost imperceptibly; the five milky eyes rotate without focus; worms move under the skin of the shoulder. Nothing else moves. |
| 12 | 06:12 | 4 | `d3_kill` | The pale chrysalis pulses once and deflates with a wet, soft shudder; steam rises faster. Static camera. |
| 13 | 06:42 | 4 | `d4_hide` | Sunny flattens against the rock; his knuckles whiten on the chain; his eyes flick sideways twice, calculating. |
| 14 | 07:10 | 5 | `d7_king_head` | Low angle: the head turns slowly toward a sound, the milky eyes sliding; the jaw tendrils twitch. |
| 15 | 08:20 | 5 | `e2_hero` | The young soldier's jaw tightens; the hand on the sheathed blade closes; the wind moves his torn coat. Slight push-in. |
| 16 | 08:30 | 5 | `e3_collapse` | He drops onto his knees, coughs, dark spittle stringing to the stone; the water skin rolls and spills. The camera pulls back a step. |
| 17 | 08:52 | 4 | `e5_bell` | The tarnished bell turns a fraction in the dirty palm, its single highlight sliding across the metal. Everything else still. |
| 18 | 09:02 | 6 | `e6_silhouette` | Almost black frame: the silhouette breathes, barely; the tiny glint of the bell vibrates with the ring. The ring echoes visually as a faint ripple. |
| 19 | 10:05 | 5 | `f2_crawl` | He drags himself forward, forearms pulling, breath misting; the camera tracks with him at floor level. |
| 20 | 10:42 | 6 | `f4_shadows` | Enormous blurred shadows surge out of the walls and coil around the shape in the centre; dust and light bend; the frame shudders on impact. |
| 21 | 11:18 | 6 | `f5_stars` | Slow drift across the starfield; faint nebula breathing; a few stars twinkle. |
| 22 | 11:38 | 5 | `f6_eyes_final` | The eyes open wider by a hair, pupils contracting; a reflection of stars shifts in the cornea. Micro push-in. |
| 23 | 12:04 | 5 | `g1_corridor` | Vapour pours off the open capsule and slides along the linoleum; one fluorescent tube stutters. Slow push down the corridor. |
| 24 | 12:20 | 5 | `g2_jet` | Jet straightens off the wall, tilts her head, and her slight smile settles; the corridor light flickers. |
| 25 | 12:32 | 5 | `g3_mirror` | The reflection looks back without blinking; his jaw sets. The mirror surface has a faint uneven wobble. |
| 26 | 12:52 | 6 | `g4_back_corridor` | The two small figures walk away down the corridor; their shadows lengthen; a dead tube buzzes. Very slow pull-back. |

**Настройки генерации:** 5–10 с на клип, движение камеры «slow», агрессивность движения 3–5/10,
seed фиксировать по номеру склейки — так повторные генерации остаются в одном стиле.
Для сцен с монстром — motion 2/10: он должен двигаться почти незаметно.

## Как собрать готовое видео из клипов

1. Положить клипы в `clips/` с именами по таймкодам (например, `00-49_a6_flash_child.mp4`).
2. `src/render2.py` заменить чтение плейта на чтение клипа: вместо
   `-i plate.jpg -vf "zoompan=..."` использовать `-i clip.mp4 -vf "scale=1280:720,fps=24"`,
   при необходимости добавив тот же `noise` и грейд.
3. Всё остальное (звук, субтитры, титры, зерно) уже готово и подхватится как есть —
   `src/score.py`, `src/mix.py`, `src/subs.py`, `src/finalize2.py` работают от абсолютных таймкодов.

Именно этот путь даёт настоящую анимацию: движение рисует видеомодель, а монтаж,
звук и цвет остаются за пайплайном.
