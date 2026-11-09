#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор демонстрационного блока «плеер + волна + «Диалог» + расшифровка».

Блок повторяет карточку звонка панели Fonotext (#244): одна полоса громкости
внутри плеера, таймлайн реплик по ролям, фразы расшифровки и таймкоды — триггеры
одной навигации. Скрипт создаёт демо-запись (синтетическая «речь», не настоящий
разговор клиента) и печатает готовую разметку волны (SVG) и таймлайна (HTML): её вставляют
в страницу один раз, без серверного рендера.

    python3 tools/build-audio-timeline.py --wav docs/demo/call-gift-0001/call.wav
    python3 tools/build-audio-timeline.py --from-wav docs/demo/call-gift-0001/call.wav
    python3 tools/build-audio-timeline.py --from-wav call.wav --segments-json segments.json

--segments-json принимает файл вида {"duration": 28.6, "segments": [{"start", "end", "role",
"text"}]} — расписание реальной записи; тогда разметка строится по нему, а не по
встроенному синтетическому таймингу. Пики волны всегда считаются из wav (--from-wav).

Воспроизведение текущего call.wav демо-карточки (реплики SpeechKit jane/ermil уже
собраны в запись; сам wav в репо, повторная озвучка не нужна):

    python3 tools/build-audio-timeline.py \
        --segments-json tools/build-audio-timeline.segments.json \
        --from-wav docs/demo/call-gift-0001/call.wav --html

Файл tools/build-audio-timeline.segments.json — каноническое расписание записи
(duration и границы реплик); разметка страниц собирается по нему. Параметр --wav
синтезирует только демонстрационный stand-in из SEGMENTS ниже и для боевой
сборки не используется.

Зависимостей нет — стандартная библиотека.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import random
import struct
import wave
from pathlib import Path

RATE = 8000
WAVE_BUCKETS = 160
WAVE_WIDTH = 480
WAVE_HEIGHT = 44

# УСТАРЕВШИЕ 80с — рабочие данные через --segments-json
# (tools/build-audio-timeline.segments.json). Ниже — только старый синтетический
# тайминг для stand-in записи из --wav.
SEGMENTS = (
    (1.0, 16.0, 'op', 'Добрый день! Это Оператор А из компании «Международный центр подарков». Чем помочь с подарком?'),
    (17.0, 31.0, 'cl', 'Здравствуйте, я выбираю подарок. Расскажите, чем плюшевый мишка отличается от готового набора.'),
    (31.0, 51.0, 'op', 'В набор можно добавить плюшевого мишку; упаковку и открытку подберём вместе.'),
    (51.0, 68.0, 'cl', 'Спасибо, теперь понятны состав и варианты упаковки.'),
    (68.0, 79.0, 'op', 'Подготовлю информацию о доставке; решение остаётся за вами.'),
)
DURATION = 80.0
VOICE = {'op': (172, 0.78), 'cl': (130, 0.62)}


def make_wav(path: Path) -> dict:
    """Синтетическая запись: слоговая модуляция в репликах, тишина между ними.

    Это демонстрационный сигнал, а не запись реального разговора: он нужен, чтобы
    волна выглядела как речь (паузы, разная громкость ролей), и ничего не раскрывал.
    """
    random.seed(2441)
    total = int(DURATION * RATE)
    frames = [0] * total
    for start, end, role, _ in SEGMENTS:
        base, level = VOICE[role]
        first, last = int(start * RATE), min(int(end * RATE), total)
        for index in range(first, last):
            t = (index - first) / RATE
            syllable = max(0.0, math.sin(2 * math.pi * 3.4 * t + 0.6)) ** 1.3
            swell = 0.7 + 0.3 * math.sin(2 * math.pi * 0.7 * t)
            noise = random.uniform(-0.22, 0.22)
            value = level * syllable * swell * (0.72 * math.sin(2 * math.pi * base * t) + 0.28 * noise)
            frames[index] = int(max(-1.0, min(1.0, value)) * 31000)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(RATE)
        writer.writeframes(struct.pack('<%dh' % len(frames), *frames))
    return {'path': path, 'duration': DURATION}


def peaks(path: Path) -> list:
    """Пики по 160 корзинам (максимум по каналам) — та же нормализация, что в панели."""
    with wave.open(str(path), 'rb') as reader:
        frames = reader.getnframes()
        step = max(1, frames // WAVE_BUCKETS)
        values = []
        while len(values) < WAVE_BUCKETS:
            chunk = reader.readframes(step)
            if not chunk:
                break
            samples = array.array('h')
            samples.frombytes(chunk[:len(chunk) - len(chunk) % 2])
            values.append(max(max(samples), -min(samples)) / 32768.0 if samples else 0.0)
        values += [0.0] * (WAVE_BUCKETS - len(values))
        top = max(values) or 1.0
        return [value / top for value in values[:WAVE_BUCKETS]]


def wave_svg(levels: list, duration: float) -> str:
    """Одна полоса: два пути (база и прогресс), без подписей и легенды."""
    middle, half_max = WAVE_HEIGHT / 2.0, WAVE_HEIGHT / 2.0 - 1.5
    step = WAVE_WIDTH / float(len(levels))
    commands = []
    for index, level in enumerate(levels):
        half = 0.75 + level * half_max
        commands.append('M%.1f %.1fV%.1f' % (step * (index + 0.5), middle - half, middle + half))
    path = ''.join(commands)
    return ('<div class="fxa-wave" data-duration="%s">'
            '<svg viewBox="0 0 %d %d" preserveAspectRatio="none" aria-hidden="true" focusable="false">'
            '<path class="fxa-wave-base" d="%s"/>'
            '<path class="fxa-wave-played" d="%s"/></svg></div>'
            % (num_text(duration), WAVE_WIDTH, WAVE_HEIGHT, path, path))


def num_text(value: float) -> str:
    text = ('%.1f' % value).rstrip('0').rstrip('.')
    return text


def clock(value: float) -> str:
    return '%d:%02d' % divmod(int(round(value)), 60)


LANES = (('op', 'Оператор'), ('cl', 'Клиент'))
MARKS = (('seg-3', 'danger'), ('seg-4', 'accent'))


def dialog_html(segments: tuple, duration: float) -> str:
    """Таймлайн реплик — HTML, а не SVG.

    Дорожки лежат в обычных блоках, реплики позиционируются процентами: на узком
    экране (390) подписи и таймкоды остаются читаемыми, тогда как SVG при
    масштабировании до 342 px превращал текст в 3–4 пикселя.
    """
    def percent(value: float) -> str:
        return ('%.2f' % (value / duration * 100)).rstrip('0').rstrip('.')

    parts = ['<div class="fxa-chart" role="group" aria-label="Таймлайн диалога: %d реплик, %s">'
             % (len(segments), clock(duration))]
    marks = []
    for target, kind in MARKS:
        if 1 <= int(target.split('-')[1]) <= len(segments):
            marks.append((segments[int(target.split('-')[1]) - 1][0], kind, target))
    for role, label in LANES:
        bars = [(start, end, index) for index, (start, end, seg_role, _)
                in enumerate(segments, 1) if seg_role == role]
        parts.append('<div class="fxa-lane"><span class="fxa-lane-name">%s</span>'
                     '<div class="fxa-rail">' % label)
        for at, kind, target in marks:
            if target in ('seg-%d' % index for _, _, index in bars):
                parts.append('<a class="fxa-hit fxa-mark fxa-mark--%s" href="#%s" data-start="%s" '
                             'style="left:%s%%"><span class="fxa-sr">Находка на %s — слушать '
                             'с этого места</span></a>'
                             % (kind, target, num_text(at), percent(at), clock(at)))
        for start, end, index in bars:
            parts.append('<a class="fxa-hit fxa-bar fxa-bar--%s" href="#seg-%d" data-start="%s" '
                         'data-end="%s" style="left:%s%%;width:%s%%"><span class="fxa-sr">'
                         'Реплика %s — %s, %s. Слушать с этого места</span></a>'
                         % (role, index, num_text(start), num_text(end), percent(start), percent(end - start),
                            clock(start), clock(end), label.lower()))
        parts.append('</div></div>')
    axis = axis_marks(duration)
    parts.append('<div class="fxa-axis">%s</div>'
                 % ''.join('<span>%s</span>' % clock(value) for value in axis))
    parts.append('</div>')
    return ''.join(parts)


def axis_marks(duration: float) -> tuple:
    """Подписи оси: ноль, круглый шаг (5–10 с) и итоговая длительность."""
    step = 10 if duration > 40 else 5
    values = [value for value in range(0, int(duration), step) if value]
    return tuple([0] + values + [round(duration, 1)]) if values else (0, round(duration, 1))


def transcript_html(segments: tuple) -> str:
    speakers = {'op': 'Оператор', 'cl': 'Клиент'}
    parts = []
    for index, (start, end, role, text) in enumerate(segments, 1):
        parts.append('<p class="fxa-seg" id="seg-%d" data-start="%s" data-end="%s">'
                     '<a class="fxa-time" href="#seg-%d" data-start="%s">%s</a>'
                     '<b class="fxa-speaker">%s</b> %s</p>'
                     % (index, num_text(start), num_text(end), index, num_text(start),
                        clock(start), speakers[role], text))
    return ''.join(parts)


def load_segments_json(path: Path) -> dict:
    data = json.loads(path.read_text())
    segments = tuple((seg['start'], seg['end'], seg['role'], seg['text'])
                     for seg in data['segments'])
    return {'segments': segments, 'duration': float(data['duration'])}


def main() -> int:
    parser = argparse.ArgumentParser(description='Демо-блок плеера и таймлайна для сайта')
    parser.add_argument('--wav', default=None, help='куда положить демо-запись')
    parser.add_argument('--from-wav', default=None, metavar='PATH',
                        help='взять готовый wav и напечатать разметку волны по нему')
    parser.add_argument('--segments-json', default=None, metavar='PATH',
                        help='JSON с расписанием реплик: duration и segments (start, end, role, text)')
    parser.add_argument('--html', action='store_true',
                        help='напечатать разметку: волна (SVG) и таймлайн (HTML)')
    args = parser.parse_args()
    timing = {'segments': SEGMENTS, 'duration': DURATION}
    if args.segments_json:
        timing = load_segments_json(Path(args.segments_json))
    wav_path = Path(args.from_wav) if args.from_wav else (
        Path(args.wav) if args.wav else Path('docs/demo/call-gift-0001/call.wav'))
    if args.from_wav:
        print(wave_svg(peaks(Path(args.from_wav)), timing['duration']))
    if args.wav:
        made = make_wav(Path(args.wav))
        levels = peaks(made['path'])
        print('wav:', made['path'], made['path'].stat().st_size, 'bytes',
              '| пиков: %d, максимум: %.2f' % (len(levels), max(levels)))
    if args.html:
        print(wave_svg(peaks(wav_path), timing['duration']))
        print(dialog_html(timing['segments'], timing['duration']))
        print(transcript_html(timing['segments']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
