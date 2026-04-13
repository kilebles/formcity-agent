# Развёртывание бота на сервере

## Сервер

- Бот: `respect@fcs-ai`, директория `/opt/formcity-agent`
- Шара с таблицами: `\\192.168.31.25\Share2\FormulaCity\iichatbot`

---

## 1. Установка зависимостей

```bash
sudo apt install -y cifs-utils
```

---

## 2. Файл с credentials для SMB

```bash
sudo mkdir -p /etc/samba
sudo nano /etc/samba/iichat.creds
```

Содержимое:

```
username=iichat
password=REDACTED
domain=fc
```

Закрыть доступ к файлу:

```bash
sudo chmod 600 /etc/samba/iichat.creds
```

---

## 3. Точка монтирования

```bash
sudo mkdir -p /opt/formcity-agent/common
```

---

## 4. Автомонтирование через fstab

```bash
sudo nano /etc/fstab
```

Добавить строку в конец:

```
//192.168.31.25/Share2/FormulaCity/iichatbot /opt/formcity-agent/common cifs credentials=/etc/samba/iichat.creds,iocharset=utf8,uid=respect,gid=respect,file_mode=0644,dir_mode=0755,_netdev 0 0
```

---

## 5. Примонтировать и проверить

```bash
sudo mount -a
ls /opt/formcity-agent/common
```

Должны появиться xlsx-файлы.

---

## 6. Установка Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker respect
newgrp docker
```

---

## 7. Настройка .env

```bash
nano /opt/formcity-agent/.env
```

```
BOT_TOKEN=...
OPENAI_KEY=...
OPENAI_MODEL=gpt-4o
TAVILY_KEY=...
```

---

## 8. Запуск

```bash
cd /opt/formcity-agent
docker compose up -d --build
```

Проверить логи:

```bash
docker compose logs -f
```

---

## Обновление бота

```bash
cd /opt/formcity-agent
sudo git pull
docker compose up -d --build
```
