#!/bin/bash
cd "$(dirname "$0")"

# Активация виртуального окружения
if [ -d "venv/bin" ]; then
  source venv/bin/activate
else
  echo "Виртуальное окружение не найдено! Создаю..." 
  python3 -m venv venv
  source venv/bin/activate
  pip install --quiet -r requirements.txt
fi

# Убить все процессы, которые слушают порт 8003
PIDS=$(lsof -ti tcp:8003)
if [ ! -z "$PIDS" ]; then
  echo "Завершаю процессы на 8003: $PIDS"
  kill -9 $PIDS
  sleep 2
fi

echo "Запускаю сервер..."
uvicorn main:app --port 8003 &

# Ждём, пока порт 8003 реально не станет доступен
while ! nc -z localhost 8003; do
  sleep 1
done

# Сбросить состояние перед открытием браузера
curl -s -X POST http://localhost:8003/reset > /dev/null

echo "Открываю браузер..."
open -a "Google Chrome" http://localhost:8003

wait
