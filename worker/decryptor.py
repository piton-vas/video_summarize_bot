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
    import gc
    
    if AudioSegment is None:
        set_status("Ошибка: библиотека pydub не установлена")
        return None
    
    if whisper is None:
        set_status("Ошибка: библиотека whisper не установлена")
        return None

    mp3_path = None
    try:
        # 1. Конвертация в mp3
        set_status("Конвертация в mp3...")
        mp3_path = await convert_to_mp3(file_path)
        
        if mp3_path is None:
            set_status("Ошибка конвертации в MP3")
            return None

        # 2. Транскрибация с таймкодами
        set_status("Транскрибация аудио (whisper)...")
        try:
            result = await transcribe_with_whisper(mp3_path, set_status=set_status)
            if result is None:
                set_status("Ошибка транскрибации: результат отсутствует.")
                return None
            transcript, segments = result
            
            # Очищаем память после транскрибации
            del result
            gc.collect()
            
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

        # 4. Сохраняем результаты
        set_status("Сохранение результатов...")
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
            
    finally:
        # Удаляем промежуточный MP3 файл для экономии места
        if mp3_path and os.path.exists(mp3_path) and mp3_path != file_path:
            try:
                os.unlink(mp3_path)
            except Exception as e:
                print(f"Не удалось удалить {mp3_path}: {e}")
        
        # Принудительная очистка памяти
        gc.collect()

async def convert_to_mp3(file_path):
    # Сохраняем mp3 рядом с исходным файлом
    base_dir = os.path.dirname(file_path)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    mp3_path = os.path.join(base_dir, base_name + ".mp3")

    if os.path.isfile(mp3_path):
        return mp3_path

    loop = asyncio.get_event_loop()
    def _convert():
        import subprocess
        
        # Используем ffmpeg напрямую для эффективной обработки больших файлов
        ffmpeg_cmd = [
            'ffmpeg', '-i', file_path,
            '-acodec', 'libmp3lame',  # MP3 кодек
            '-ab', '64k',             # Низкий битрейт для экономии памяти
            '-ac', '1',               # Моно звук (экономия памяти)
            '-ar', '16000',           # 16кГц (оптимально для речи)
            '-map', '0:a',            # Только аудио дорожка
            '-y',                     # Перезаписать файл
            mp3_path
        ]
        
        try:
            # Выполняем конвертацию через ffmpeg (более эффективно по памяти)
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=1800)
            
            if result.returncode == 0 and os.path.exists(mp3_path):
                return mp3_path
            else:
                print(f"ffmpeg error: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("ffmpeg timeout - файл слишком большой, используем альтернативный метод")
        except Exception as e:
            print(f"ffmpeg failed: {e}")
            
        # Fallback: используем pydub с оптимизациями
        try:
            # Загружаем файл в pydub с ограничениями
            audio = AudioSegment.from_file(file_path)
            
            # Применяем оптимизации для экономии памяти
            audio = audio.set_channels(1)       # Моно
            audio = audio.set_frame_rate(16000) # 16кГц
            
            # Экспортируем с низким битрейтом
            audio.export(mp3_path, format="mp3", bitrate="64k")
            
            return mp3_path
            
        except Exception as e:
            print(f"pydub conversion error: {e}")
            return None
            
    return await loop.run_in_executor(None, _convert)

async def transcribe_with_whisper(mp3_path, set_status=None):
    loop = asyncio.get_event_loop()
    def _transcribe():
        import gc
        import torch
        
        # Проверяем размер файла
        file_size = os.path.getsize(mp3_path) / (1024 * 1024)  # МБ
        
        if file_size > 5:  # Файлы больше 5 МБ обрабатываем частями для экономии памяти
            return _transcribe_large_file(mp3_path, set_status)
        else:
            return _transcribe_small_file(mp3_path, set_status)
    
    def _transcribe_small_file(mp3_path, set_status):
        import gc
        import torch
        import os
        
        # Дополнительная очистка перед загрузкой модели
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        if set_status:
            file_size = os.path.getsize(mp3_path) / (1024 * 1024)
            set_status(f"Загружаю модель для файла {file_size:.1f}МБ...")
        
        # Загружаем модель с минимальными настройками
        model = whisper.load_model("tiny", device="cpu")  # Принудительно CPU
        
        if set_status:
            set_status("Начинаю транскрибацию...")
        
        # Транскрибируем с минимальными настройками для экономии памяти
        result = model.transcribe(
            mp3_path, 
            word_timestamps=True, 
            verbose=False,
            no_speech_threshold=0.6,  # Более строгий порог тишины
            logprob_threshold=-1.0    # Упрощаем обработку
        )
        
        transcript = result["text"]
        segments = result["segments"]
        
        # Очищаем результат из памяти
        del result
        gc.collect()
        
        processed_text = ""
        processed_segments = []
        total = len(segments)
        
        for idx, seg in enumerate(segments):
            processed_text += seg["text"]
            processed_segments.append(seg)
            if set_status and idx % 10 == 0:  # Обновляем статус реже
                set_status(f"Обработка: сегмент {idx+1} из {total}")
            
            # Периодическая очистка памяти
            if idx % 50 == 0:
                gc.collect()
        
        # Финальная очистка памяти
        del model, segments
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        return processed_text, processed_segments
    
    def _transcribe_large_file(mp3_path, set_status):
        """Обработка больших файлов по частям для экономии памяти"""
        import gc
        import torch
        import subprocess
        import tempfile
        
        if set_status:
            set_status("Большой файл - обрабатываю по частям...")
        
        # Получаем длительность файла
        duration_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', mp3_path]
        try:
            duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
            import json
            duration_info = json.loads(duration_result.stdout)
            total_duration = float(duration_info['format']['duration'])
        except:
            total_duration = 3600  # По умолчанию 1 час
        
        # Обрабатываем файл частями по 5 минут для экономии памяти
        chunk_duration = 300  # 5 минут
        chunks_count = int(total_duration / chunk_duration) + 1
        
        all_text = ""
        all_segments = []
        time_offset = 0
        
        model = whisper.load_model("tiny", device="cpu")  # Принудительно CPU для экономии памяти
        
        for chunk_idx in range(chunks_count):
            if set_status:
                set_status(f"Обрабатываю часть {chunk_idx + 1} из {chunks_count}...")
            
            start_time = chunk_idx * chunk_duration
            
            # Создаем временный файл для части
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_chunk_path = temp_file.name
            
            try:
                # Извлекаем часть файла
                chunk_cmd = [
                    'ffmpeg', '-i', mp3_path,
                    '-ss', str(start_time),
                    '-t', str(chunk_duration),
                    '-acodec', 'copy',
                    '-y', temp_chunk_path
                ]
                
                subprocess.run(chunk_cmd, capture_output=True)
                
                # Проверяем, что файл создался
                if not os.path.exists(temp_chunk_path) or os.path.getsize(temp_chunk_path) < 1024:
                    break
                
                # Транскрибируем часть
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                result = model.transcribe(temp_chunk_path, word_timestamps=True, verbose=False)
                
                # Добавляем результат с корректировкой времени
                chunk_text = result["text"]
                all_text += chunk_text
                
                for seg in result["segments"]:
                    seg['start'] += start_time
                    seg['end'] += start_time
                    all_segments.append(seg)
                
                # Очищаем память
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
            finally:
                # Удаляем временный файл
                if os.path.exists(temp_chunk_path):
                    os.unlink(temp_chunk_path)
        
        # Очищаем модель
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return all_text, all_segments
    
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



