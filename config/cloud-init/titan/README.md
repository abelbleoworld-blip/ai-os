# Cloud-init для titan (Beelink AZW SER9)

Безголовая установка Ubuntu Server 24.04 LTS с готовым SSH, Docker, Node 22, WireGuard.

## Что получится после установки

- hostname: `titan`
- user: `abel` (пароль `changeme123` — **сменить!**), sudo без пароля → нет, через пароль
- SSH ключ MC3 (forge) уже в `~abel/.ssh/authorized_keys`
- Docker + compose-plugin, Node 22, Python 3, git, htop, tmux, jq
- WireGuard готов к подключению (конфиг конкретного peer — отдельным шагом)
- UFW: 22, 51820/udp (WG), 8080/tcp (AI-OS)
- Avahi (mDNS) — `titan.local` резолвится в LAN
- Часовая зона Europe/Moscow

## Подготовка USB-флешки (на forge / любом Linux/macOS)

Вариант A — **двойная флешка** (рекомендуется, надёжно):

1. Записать ISO Ubuntu Server 24.04 на флешку #1:
   ```bash
   diskutil unmountDisk /dev/diskN          # macOS, найти через `diskutil list`
   sudo dd if=ubuntu-24.04.1-live-server-amd64.iso of=/dev/rdiskN bs=4m status=progress
   ```
2. На флешке #2 (любая, ≥1 ГБ) создать FAT32-раздел с меткой **`CIDATA`**, скопировать в корень `user-data` и `meta-data`.
3. Воткнуть **обе** флешки в Beelink, загрузиться с #1 (F7 → boot menu) — установщик найдёт cloud-init.

Вариант B — **одна флешка с двумя разделами**:

1. Сделать ISO USB как в А.1
2. Добавить второй раздел FAT32 с меткой `CIDATA` через `gparted` (Linux) или `diskutil` (macOS, сложнее — лучше gparted).
3. Скопировать в него `user-data` + `meta-data`.

Вариант C — **через сеть** (когда titan уже умеет в LAN):
   - запустить локальный HTTP-сервер с `user-data`/`meta-data`
   - в grub при загрузке Ubuntu Server: `e` → добавить `autoinstall ds=nocloud-net;s=http://10.0.0.146:8000/`

## Шаги на Beelink AZW SER9

1. Воткнуть USB. Включить.
2. Сразу жать `F7` (boot menu) или `Del/F2` (BIOS) — выбрать USB.
3. В BIOS убедиться: Secure Boot **off**, Boot Mode **UEFI**, USB первым.
4. Выбрать `Try or Install Ubuntu Server`.
5. Если cloud-init найден — установка пройдёт автоматически (~10–15 мин).
6. Если **не** найден — установщик спросит «Continue with autoinstall?» — Yes.
7. После reboot вынуть USB → проверить `ping titan.local` с forge.

## Проверка после загрузки

С forge:

```bash
ssh abel@titan.local 'cat /etc/titan-cloud-init.done; docker --version; node --version'
```

Ожидается:
```
titan ready 2026-04-26T...
Docker version 27.x
v22.x.x
```

## Сразу после первого входа — обязательное

```bash
# 1. Сменить пароль (текущий "changeme123")
passwd

# 2. Подключиться к WG (получить .conf от vps-brand admin)
sudo cp titan.conf /etc/wireguard/wg0.conf
sudo systemctl enable --now wg-quick@wg0
sudo wg show

# 3. Добавить host alias на forge
echo 'Host titan
    HostName 10.0.0.133   # или WG-IP, например 10.10.0.8
    User abel
    IdentityFile ~/.ssh/vps_abel_key
    IdentitiesOnly yes' >> ~/.ssh/config
```

## Деплой AI-OS на titan (после готовности)

```bash
# с forge
cd ~/ai-os
ssh titan 'mkdir -p ~/ai-os'
rsync -aAX --delete --exclude='.git' --exclude='node_modules' --exclude='__pycache__' \
    ./ titan:~/ai-os/
ssh titan 'cd ~/ai-os && bash deploy.sh'
```

## Если что-то пошло не так

- ISO не грузится → проверить SHA256, перезаписать с `bs=4m` (macOS) или `bs=4M` (Linux)
- cloud-init проигнорирован → проверить метку раздела ровно `CIDATA` (заглавные)
- SSH не пускает → ключ в `authorized-keys` сейчас vps_abel_key.pub (forge), для других forge'ей добавить вручную
- Что-то ещё → лог: `cat /var/log/cloud-init-output.log` и `journalctl -u cloud-final`
