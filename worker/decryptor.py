import os
import sys
import asyncio
import tempfile
try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None
try:
    import whisper
except ImportError:
    whisper = None

def format_time(seconds):
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02}:{m:02}:{s:02}:{ms:03}"

async def decrypt_process(file_path, set_status):
    if AudioSegment is None:
        set_status("Ошибка: библиотека pydub не установлена")
        return None
    
    if whisper is None:
        set_status("Ошибка: библиотека whisper не установлена")
        return None

    # 1. Конвертация в mp3
    set_status("Конвертация в mp3...")
    mp3_path = await convert_to_mp3(file_path)

    # 2. Транскрибация с таймкодами
    set_status("Транскрибация аудио (whisper)...")
    try:
        result = await transcribe_with_whisper(mp3_path, set_status=set_status)
        if result is None:
            set_status("Ошибка транскрибации: результат отсутствует.")
            return None
        transcript, segments = result
    except Exception as e:
        set_status(f"Ошибка транскрибации: {e}")
        return None

    # 3. Саммаризация текста
    set_status("Саммаризация текста...")
    try:
        summary = await summarize_text(transcript)
    except Exception as e:
        set_status(f"Ошибка саммаризации: {e}")
        return None

    # Сохраняем результаты
    try:
        out_path = os.path.splitext(file_path)[0] + "_summary.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("Summary:\n" + summary + "\n\n")
            f.write("Transcript:\n" + transcript + "\n\n")
            f.write("Segments:\n")
            for seg in segments:
                start = format_time(seg['start'])
                end = format_time(seg['end'])
                f.write(f"[{start} - {end}] {seg['text']}\n")
        
        return {
            'summary': summary,
            'transcript': transcript,
            'segments': segments,
            'output_file': out_path
        }
    except Exception as e:
        set_status(f"Ошибка сохранения файла: {e}")
        return None

async def convert_to_mp3(file_path):
    # Сохраняем mp3 рядом с исходным файлом
    base_dir = os.path.dirname(file_path)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    mp3_path = os.path.join(base_dir, base_name + ".mp3")

    if os.path.isfile(mp3_path):
        return mp3_path

    loop = asyncio.get_event_loop()
    def _convert():
        audio = AudioSegment.from_file(file_path)
        audio.export(mp3_path, format="mp3")
        return mp3_path
    return await loop.run_in_executor(None, _convert)

async def transcribe_with_whisper(mp3_path, set_status=None):
    loop = asyncio.get_event_loop()
    def _transcribe():
        model = whisper.load_model("base")
        result = model.transcribe(mp3_path, word_timestamps=True, verbose=False)
        transcript = result["text"]
        segments = result["segments"]
        processed_text = ""
        processed_segments = []
        total = len(segments)
        for idx, seg in enumerate(segments):
            processed_text += seg["text"]
            processed_segments.append(seg)
            if set_status:
                set_status(f"Транскрибация: сегмент {idx+1} из {total}")
        return processed_text, processed_segments
    return await loop.run_in_executor(None, _transcribe)

async def summarize_text(text):
    # Простейшая заглушка для саммаризации
    # Здесь можно подключить любую модель/библиотеку для саммаризации
    return text[:500] + ("..." if len(text) > 500 else "")

if __name__ == "__main__":
    import sys

    async def main():
        if len(sys.argv) < 2:
            print("Usage: python decryptor.py <path_to_file>")
            return
        file_path = sys.argv[1]
        def set_status(msg):
            print(msg)
        await decrypt_process(file_path, set_status)

    asyncio.run(main())



