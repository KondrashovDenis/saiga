# nvidia-uvm.service

Headless-сервер без X создаёт `/dev/nvidia0..N` при загрузке драйвера, но
**не** `/dev/nvidia-uvm` и `/dev/nvidia-uvm-tools` — их обычно создаёт первый
CUDA-процесс или X-сервер. Без этих device nodes Docker `runtime: nvidia`
падает на старте контейнера.

Этот юнит запускает `nvidia-modprobe -u -c=0..N` при boot до docker.service,
чтобы UVM был готов к моменту запуска LLM-контейнера.

## Установка

```bash
sudo cp llm/systemd/nvidia-uvm.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nvidia-uvm.service
sudo systemctl status nvidia-uvm.service
```

После этого `ls /dev/nvidia-uvm` должен показывать существующий device.

## Под другую конфигурацию GPU

Если у вас N GPU (не 3) — отредактируйте `ExecStart`:
```
ExecStart=/usr/bin/nvidia-modprobe -u -c=0 -c=1 ... -c=N-1
```
