#!/bin/bash
# Улучшенный скрипт для тестирования производительности LLM

# Функция для очистки при завершении
cleanup() {
  echo "Очистка процессов мониторинга..."
  # Убиваем все фоновые процессы мониторинга
  kill $(jobs -p) 2>/dev/null
  pkill -f "docker stats $MODEL_CONTAINER" 2>/dev/null
  rm -f /tmp/monitor_*.txt /tmp/gpu_monitor_*.txt
  echo "Очистка завершена."
}

# Устанавливаем trap для очистки при выходе из скрипта
trap cleanup EXIT INT TERM

# Настройка параметров
MODEL_CONTAINER="saiga-llm"
RESULT_FILE="llm_benchmark_detailed.csv"
TEST_PROMPTS=(
  "Объясни основные принципы теории относительности Эйнштейна"
  "Напиши короткий рассказ о приключениях космонавта на Марсе"
  "Что такое квантовый компьютер и как он работает?"
  "Объясни подробно технологию блокчейн и её применение в современном мире"
  "Составь список из 10 самых важных событий 21 века и объясни их значение"
)

# Проверка существования контейнера перед началом
if ! docker ps | grep -q "$MODEL_CONTAINER"; then
  echo "Ошибка: Контейнер $MODEL_CONTAINER не запущен!"
  exit 1
fi

# Подготовка файла результатов
echo "prompt,time_seconds,response_length,max_cpu_perc,max_mem_usage,max_gpu0_util,max_gpu1_util,max_gpu2_util" > $RESULT_FILE

# Функция для запуска одного теста с постоянным мониторингом
run_test() {
  local prompt="$1"
  local test_id=$(date +%s)
  local monitor_file="/tmp/monitor_${test_id}.txt"
  local gpu_monitor_file="/tmp/gpu_monitor_${test_id}.txt"
  
  echo "==========================================="
  echo "Тестируем запрос: $prompt"
  echo "==========================================="
  
  # Повторная проверка существования контейнера
  if ! docker ps | grep -q "$MODEL_CONTAINER"; then
    echo "Ошибка: Контейнер $MODEL_CONTAINER был остановлен во время тестирования!"
    return 1
  fi
  
  # Запускаем процесс мониторинга в фоне
  (
    while docker ps | grep -q "$MODEL_CONTAINER"; do
      docker stats $MODEL_CONTAINER --no-stream --format "{{.CPUPerc}} {{.MemPerc}} {{.MemUsage}}" >> $monitor_file
      nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader >> $gpu_monitor_file
      sleep 0.5
    done
  ) &
  MONITOR_PID=$!
  
  # Отправляем запрос к API и засекаем время
  local start_time=$(date +%s.%N)
  local api_response=$(curl -s -X POST "http://localhost:5000/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"saiga_nemo_12b.Q4_K_M.gguf\",
      \"messages\": [{\"role\": \"user\", \"content\": \"$prompt\"}],
      \"temperature\": 0.7,
      \"max_tokens\": 512,
      \"stream\": false
    }"
  )
  local end_time=$(date +%s.%N)
  
  # Останавливаем мониторинг
  if kill $MONITOR_PID 2>/dev/null; then
    echo "Процесс мониторинга остановлен."
  else
    echo "Не удалось остановить процесс мониторинга, возможно он уже завершен."
  fi
  sleep 1
  
  # Обрабатываем результаты мониторинга
  if [ -f "$monitor_file" ]; then
    max_cpu=$(cat $monitor_file | awk '{print $1}' | sed 's/%//' | sort -nr | head -1)
    max_mem=$(cat $monitor_file | awk '{print $3}' | head -1)
  else
    max_cpu="N/A"
    max_mem="N/A"
  fi
  
  # Обрабатываем результаты мониторинга GPU
  if [ -f "$gpu_monitor_file" ]; then
    max_gpu0=$(cat $gpu_monitor_file | awk 'NR % 3 == 1 {print $1}' | sort -nr | head -1)
    max_gpu1=$(cat $gpu_monitor_file | awk 'NR % 3 == 2 {print $1}' | sort -nr | head -1)
    max_gpu2=$(cat $gpu_monitor_file | awk 'NR % 3 == 3 {print $1}' | sort -nr | head -1)
  else
    max_gpu0="N/A"
    max_gpu1="N/A"
    max_gpu2="N/A"
  fi
  
  # Вычисляем время выполнения
  local elapsed=$(echo "$end_time - $start_time" | bc)
  
  # Обрабатываем результат запроса
  local response_content=$(echo "$api_response" | grep -o '"content":"[^"]*"' | head -1 | sed 's/"content":"//;s/"$//')
  local response_length=$(echo -n "$response_content" | wc -c)
  
  # Выводим результаты
  echo "Время выполнения: $elapsed секунд"
  echo "Максимальная загрузка CPU: $max_cpu%"
  echo "Использование памяти: $max_mem"
  echo "Максимальная загрузка GPU 0: $max_gpu0%"
  echo "Максимальная загрузка GPU 1: $max_gpu1%"
  echo "Максимальная загрузка GPU 2: $max_gpu2%"
  echo "Длина запроса: $(echo -n "$prompt" | wc -c) символов"
  echo "Длина ответа: $response_length символов"
  echo "Начало ответа: ${response_content:0:100}..."
  
  # Сохраняем результаты в лог
  echo "\"$prompt\",$elapsed,$response_length,$max_cpu,$max_mem,$max_gpu0,$max_gpu1,$max_gpu2" >> $RESULT_FILE
  
  # Удаляем временные файлы
  rm -f $monitor_file $gpu_monitor_file
  
  echo "==========================================="
  echo ""
}

# Запуск всех тестов
for prompt in "${TEST_PROMPTS[@]}"; do
  run_test "$prompt"
  # Пауза между тестами
  sleep 5
done

echo "Тестирование завершено. Результаты сохранены в $RESULT_FILE"
# cleanup будет вызван автоматически благодаря trap
