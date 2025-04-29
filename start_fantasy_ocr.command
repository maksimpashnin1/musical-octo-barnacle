#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

# Убить все процессы, которые слушают порт 8001
PIDS=$(lsof -ti tcp:8001)
if [ ! -z "$PIDS" ]; then
  echo "Завершаю процессы на 8001: $PIDS"
  kill -9 $PIDS
  sleep 2
fi

echo "Запускаю сервер..."
uvicorn main:app --port 8001 &

# Ждём, пока порт 8001 реально не станет доступен
while ! nc -z localhost 8001; do
  sleep 1
done

echo "Открываю браузер..."
open -a "Google Chrome" http://localhost:8001

wait
