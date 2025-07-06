import os
import json
import logging
import asyncio
import tempfile
from datetime import datetime
from rq import Worker, Queue, Connection
import redis
from decryptor import decrypt_process

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Настройки Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Подключение к Redis для RQ (без decode_responses)
redis_conn_rq = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=False)

# Подключение к Redis для данных (с decode_responses) 
redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

class VideoProcessor:
    def __init__(self):
        self.processing_count = 0
        
    async def process_video_task(self, task_data):
        """
        Обработка видео задачи
        """
        task_id = task_data['task_id']
        file_path = task_data['file_path']
        user_id = task_data['user_id']
        
        logger.info(f"Начинаю обработку задачи {task_id} для пользователя {user_id}")
        
        try:
            # Устанавливаем статус в Redis
            self.set_task_status(task_id, "processing", "Начинаю обработку...")
            
            # Функция для обновления статуса
            def update_status(status_text):
                self.set_task_status(task_id, "processing", status_text)
                logger.info(f"Задача {task_id}: {status_text}")
            
            # Обрабатываем видео
            result = await decrypt_process(file_path, update_status)
            
            if result:
                # Сохраняем результат в Redis
                self.set_task_result(task_id, result)
                logger.info(f"Задача {task_id} завершена успешно")
            else:
                self.set_task_status(task_id, "failed", "Ошибка обработки видео")
                logger.error(f"Задача {task_id} завершена с ошибкой")
                
        except Exception as e:
            error_msg = f"Ошибка обработки: {str(e)}"
            self.set_task_status(task_id, "failed", error_msg)
            logger.error(f"Задача {task_id}: {error_msg}")
        
        finally:
            # Удаляем временный файл
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    logger.info(f"Временный файл {file_path} удален")
            except Exception as e:
                logger.error(f"Ошибка удаления файла {file_path}: {e}")
    
    def set_task_status(self, task_id, status, message=""):
        """
        Устанавливает статус задачи в Redis
        """
        try:
            task_key = f"task:{task_id}"
            task_data = {
                'status': status,
                'message': message,
                'updated_at': datetime.now().isoformat()
            }
            redis_conn.hset(task_key, mapping=task_data)
            redis_conn.expire(task_key, 3600)  # Храним 1 час
        except Exception as e:
            logger.error(f"Ошибка обновления статуса задачи {task_id}: {e}")
    
    def set_task_result(self, task_id, result):
        """
        Сохраняет результат задачи в Redis
        """
        try:
            task_key = f"task:{task_id}"
            result_data = {
                'status': 'completed',
                'result': json.dumps(result, ensure_ascii=False),
                'completed_at': datetime.now().isoformat()
            }
            redis_conn.hset(task_key, mapping=result_data)
            redis_conn.expire(task_key, 3600)  # Храним 1 час
        except Exception as e:
            logger.error(f"Ошибка сохранения результата задачи {task_id}: {e}")

def process_video_sync(task_data, timeout=None):
    """
    Синхронная обертка для async функции (для RQ)
    """
    processor = VideoProcessor()
    asyncio.run(processor.process_video_task(task_data))

def main():
    """
    Основная функция воркера
    """
    logger.info("Запуск воркера для обработки видео...")
    
    try:
        # Проверяем подключение к Redis
        redis_conn_rq.ping()
        logger.info(f"Подключен к Redis: {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        logger.error(f"Ошибка подключения к Redis: {e}")
        return
    
    # Создаем очередь
    queue = Queue('video_processing', connection=redis_conn_rq)
    
    # Создаем воркер
    worker = Worker([queue], connection=redis_conn_rq)
    
    logger.info("Воркер готов к обработке задач...")
    
    # Запуск воркера
    worker.work(with_scheduler=True)

if __name__ == "__main__":
    main() 