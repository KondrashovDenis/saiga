#!/bin/bash

# Скрипт для тестирования производительности LLM

# Настройка параметров
MODEL_CONTAINER="saiga-llm"
TEST_PROMPTS=(
  "Объясни основные принципы теории относительности Эйнштейна"
  "Напиши короткий рассказ о приключениях космонавта на Марсе"
  "Что такое квантовый компьютер и как он работает?"
  "Объясни подробно технологию блокчейн и её применение в современном мире"
  "Составь список из 10 самых важных событий 21 века и объясни их значение"
)

# Функция для запуска одного теста и сбора метрик
run_test() {
  local prompt="$1"
  local prompt_encoded=$(echo -n "$prompt" | base64)
  local start_time=$(date +%s.%N)
  
  echo "===========================================" 
  echo "Тестируем запрос: $prompt"
  echo "===========================================" 
  
  # Начинаем мониторинг
  echo "Начальные метрики CPU/RAM:"
  docker stats $MODEL_CONTAINER --no-stream --format "{{.CPUPerc}} {{.MemPerc}} {{.MemUsage}}"
  
  echo "Начальные метрики GPU:"
  nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.total,memory.free,memory.used --format=csv,noheader
  
  # Отправляем запрос к API
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
  local elapsed=$(echo "$end_time - $start_time" | bc)
  
  # Финальные метрики
  echo "Конечные метрики CPU/RAM:"
  docker stats $MODEL_CONTAINER --no-stream --format "{{.CPUPerc}} {{.MemPerc}} {{.MemUsage}}"
  
  echo "Конечные метрики GPU:"
  nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.total,memory.free,memory.used --format=csv,noheader
  
  # Вывод результатов
  echo "Время выполнения: $elapsed секунд"
  echo "Длина запроса: $(echo -n "$prompt" | wc -c) символов"
  
  # Выводим только часть ответа для краткости
  local response_content=$(echo "$api_response" | grep -o '"content":"[^"]*"' | head -1 | sed 's/"content":"//;s/"$//')
  local response_length=$(echo -n "$response_content" | wc -c)
  echo "Длина ответа: $response_length символов"
  echo "Начало ответа: ${response_content:0:100}..."
  
  # Сохраняем результаты в лог
  echo "$prompt,$elapsed,$response_length" >> llm_benchmark_results.csv
  
  echo "===========================================" 
  echo ""
}

# Подготовка файла результатов
echo "prompt,time_seconds,response_length" > llm_benchmark_results.csv

# Запуск всех тестов
for prompt in "${TEST_PROMPTS[@]}"; do
  run_test "$prompt"
  # Пауза между тестами
  sleep 5
done

echo "Тестирование завершено. Результаты сохранены в llm_benchmark_results.csv"
