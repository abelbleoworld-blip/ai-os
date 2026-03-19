"""
Начальное обучение модулей — стартовые знания.
Запустить один раз: python knowledge/seed.py
Каждый модуль получает знания под свою задачу.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.knowledge import KnowledgeBase


def train_files():
    """Обучение модуля файлов"""
    kb = KnowledgeBase("files")

    # Источники документации
    kb.add_source("Microsoft NTFS Docs", "https://learn.microsoft.com/en-us/windows-server/storage/file-server/ntfs-overview", "Документация по файловой системе NTFS")
    kb.add_source("Python pathlib", "https://docs.python.org/3/library/pathlib.html", "Работа с путями в Python")
    kb.add_source("Windows File System", "https://learn.microsoft.com/en-us/windows/win32/fileio/file-systems", "Общая документация по ФС Windows")

    # Знания
    kb.add("Максимальная длина пути Windows", "По умолчанию 260 символов (MAX_PATH). Можно снять ограничение через реестр: HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem LongPathsEnabled=1", ["path", "ограничение", "windows"], "Microsoft Docs")
    kb.add("Типы файловых систем", "NTFS — основная для Windows (журналирование, права доступа, сжатие). FAT32 — совместимость (макс файл 4GB). exFAT — для флешек и SD (нет ограничения 4GB)", ["ntfs", "fat32", "exfat", "файловая система"])
    kb.add("Временные файлы Windows", "Расположение: %TEMP% (обычно C:\\Users\\<user>\\AppData\\Local\\Temp). Безопасно удалять файлы старше текущей сессии. Команда: del /q/f %TEMP%\\*", ["temp", "очистка", "временные"], "Microsoft Docs")
    kb.add("Права доступа NTFS", "icacls — команда для управления правами. Пример: icacls file.txt /grant User:F (полный доступ). takeown /f file.txt — забрать владение", ["права", "доступ", "icacls", "ntfs"])
    kb.add("Поиск больших файлов", "PowerShell: Get-ChildItem -Path C:\\ -Recurse -File | Sort-Object Length -Descending | Select-Object -First 20 FullName, @{N='SizeMB';E={[math]::Round($_.Length/1MB,1)}}", ["поиск", "большие файлы", "место на диске"], "PowerShell")
    kb.add("Символические ссылки", "mklink /D link target — создать симлинк на папку. mklink link target — на файл. mklink /J link target — junction (только папки, не нужны права админа)", ["symlink", "ссылка", "mklink"])
    kb.add("Восстановление удалённых файлов", "Корзина: первое место поиска. Теневые копии: vssadmin list shadows. Windows File Recovery (winfr) — утилита от Microsoft для глубокого восстановления", ["восстановление", "удалённые", "корзина"])
    kb.add("Сжатие файлов", "NTFS сжатие: compact /c /s:folder — сжать папку. Экономит место, но замедляет доступ. Не рекомендуется для SSD и баз данных", ["сжатие", "compact", "ntfs"])

    # Решения проблем
    kb.add_solution("диск заполнен", "1. Очистка диска: cleanmgr /d C 2. Удалить WinSxS: Dism /Online /Cleanup-Image /StartComponentCleanup 3. Найти большие файлы: Get-ChildItem -Recurse | Sort Length -Desc | Select -First 20")
    kb.add_solution("файл занят другим процессом", "1. Resource Monitor → CPU → Associated Handles → поиск файла 2. PowerShell: Get-Process | Where-Object {$_.Modules.FileName -eq 'path'} 3. handle.exe от Sysinternals")
    kb.add_solution("нет доступа к файлу", "1. takeown /f file /r /d y 2. icacls file /grant %username%:F 3. Проверить не зашифрован ли (cipher /c file)")
    kb.add_solution("имя файла слишком длинное", "1. Включить длинные пути: reg add HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1 2. Использовать subst для сокращения пути: subst X: C:\\very\\long\\path")

    kb.save()
    print(f"  files: {len(kb.entries)} знаний, {len(kb.sources)} источников, {len(kb.solutions)} решений")


def train_processes():
    """Обучение модуля процессов"""
    kb = KnowledgeBase("processes")

    kb.add_source("Windows Process Docs", "https://learn.microsoft.com/en-us/windows/win32/procthread/processes-and-threads", "Процессы и потоки Windows")
    kb.add_source("Sysinternals", "https://learn.microsoft.com/en-us/sysinternals/", "Утилиты Sysinternals для диагностики")
    kb.add_source("PowerShell Process", "https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process", "Управление процессами через PowerShell")

    kb.add("Критические процессы Windows", "Нельзя завершать: csrss.exe (подсистема), lsass.exe (безопасность), smss.exe (менеджер сессий), wininit.exe (инициализация), services.exe (службы). Завершение = синий экран", ["критические", "системные", "bsod"], "Microsoft Docs")
    kb.add("Приоритеты процессов", "Realtime(24) > High(13) > AboveNormal(10) > Normal(8) > BelowNormal(6) > Idle(4). Менять: wmic process where name='app.exe' call setpriority 128 (High). Или PowerShell: (Get-Process app).PriorityClass = 'High'", ["приоритет", "priority"], "Microsoft Docs")
    kb.add("Автозагрузка", "Места: 1. Task Manager → Startup 2. shell:startup (текущий пользователь) 3. shell:common startup (все) 4. Реестр: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run 5. Планировщик задач", ["автозагрузка", "startup"])
    kb.add("Утечка памяти", "Признаки: процесс постоянно растёт в памяти. Диагностика: 1. Process Explorer → свойства процесса → Performance 2. RAMMap от Sysinternals 3. Windows Performance Toolkit (WPT)", ["утечка", "memory leak", "память"])
    kb.add("Зависший процесс", "1. taskkill /f /im process.exe 2. taskkill /f /pid 1234 3. PowerShell: Stop-Process -Name process -Force 4. Если не помогает: wmic process where processid=1234 call terminate", ["зависший", "kill", "завершить"])
    kb.add("Службы Windows", "sc query — список служб. sc stop ServiceName — остановить. sc start ServiceName — запустить. sc config ServiceName start=disabled — отключить. Get-Service | Where Status -eq Running", ["службы", "services", "sc"])
    kb.add("Диагностика высокой нагрузки CPU", "1. Найти процесс: Get-Process | Sort CPU -Desc | Select -First 5 2. Process Explorer → столбец CPU 3. Если svchost.exe — определить службу: tasklist /svc /fi 'PID eq 1234' 4. resmon (Resource Monitor)", ["cpu", "нагрузка", "загрузка процессора"])

    kb.add_solution("процесс не завершается", "1. taskkill /f /pid PID 2. Если 'Access Denied' — запустить от админа 3. Если защищённый процесс — pskill от Sysinternals 4. Крайний случай — перезагрузка")
    kb.add_solution("высокая загрузка CPU", "1. Определить процесс: Get-Process | Sort CPU -Desc 2. Если системный (WMI, Defender) — перезапустить службу 3. Если пользовательский — снизить приоритет или перезапустить 4. Проверить не майнер ли (неизвестный процесс с высоким CPU)")
    kb.add_solution("программа не запускается", "1. Проверить Event Viewer → Application 2. Попробовать от админа 3. Проверить зависимости: depends.exe 4. Проверить совместимость: свойства → Совместимость 5. sfc /scannow если системная")

    kb.save()
    print(f"  processes: {len(kb.entries)} знаний, {len(kb.sources)} источников, {len(kb.solutions)} решений")


def train_system():
    """Обучение модуля системной информации"""
    kb = KnowledgeBase("system")

    kb.add_source("Windows Hardware Docs", "https://learn.microsoft.com/en-us/windows-hardware/", "Документация по железу Windows")
    kb.add_source("Intel ARK", "https://ark.intel.com/", "Спецификации процессоров Intel")
    kb.add_source("Windows Performance", "https://learn.microsoft.com/en-us/windows-hardware/test/wpt/", "Windows Performance Toolkit")

    kb.add("Информация о железе", "systeminfo — полная информация. wmic cpu get name,cores,maxclockspeed — CPU. wmic memorychip get capacity,speed,manufacturer — RAM. wmic diskdrive get model,size — диски. Get-ComputerInfo — всё через PowerShell", ["железо", "hardware", "инфо"])
    kb.add("Температура компонентов", "Windows не показывает температуру по умолчанию. WMI: Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace root/wmi (не всегда работает). Надёжнее: HWiNFO64, Open Hardware Monitor, или LibreHardwareMonitor (open source)", ["температура", "нагрев", "thermal"])
    kb.add("BIOS/UEFI информация", "wmic bios get smbiosbiosversion,releasedate — версия BIOS. msinfo32 — полная информация. Обновление BIOS — только с сайта производителя!", ["bios", "uefi", "firmware"])
    kb.add("Оперативная память", "Максимум RAM зависит от: 1. Версия Windows (Home — 128GB, Pro — 2TB) 2. Материнская плата 3. Процессор. Проверить: wmic memphysical get maxcapacity. Частота: wmic memorychip get speed", ["ram", "память", "оперативная"])
    kb.add("SSD vs HDD оптимизация", "SSD: отключить дефрагментацию (включить TRIM). Проверить TRIM: fsutil behavior query disabledeletenotify (0 = включен). HDD: дефрагментация помогает. defrag C: /O — оптимизация по типу диска", ["ssd", "hdd", "оптимизация", "диск"])
    kb.add("Энергопотребление", "powercfg /energy — отчёт об энергопотреблении. powercfg /batteryreport — отчёт о батарее. Планы: powercfg /list. Высокая производительность: powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", ["энергия", "батарея", "питание"])
    kb.add("Обновления Windows", "Get-WindowsUpdate (модуль PSWindowsUpdate). wuauclt /detectnow — проверить обновления. UsoClient StartScan — Windows 10+. Просмотр: Get-HotFix | Sort InstalledOn -Desc", ["обновления", "update", "windows update"])

    kb.add_solution("мало оперативной памяти", "1. Найти что ест: Get-Process | Sort WS -Desc | Select -First 10 2. Отключить ненужные службы 3. Увеличить pagefile: sysdm.cpl → Advanced → Performance → Virtual Memory 4. Добавить RAM физически")
    kb.add_solution("система тормозит", "1. Проверить диск: CrystalDiskInfo (здоровье SSD/HDD) 2. Проверить CPU/RAM: resmon 3. Отключить визуальные эффекты: sysdm.cpl → Advanced → Performance 4. Проверить автозагрузку: Task Manager → Startup 5. sfc /scannow + DISM /RestoreHealth")
    kb.add_solution("синий экран (BSOD)", "1. Просмотр: Event Viewer → System → Critical 2. Файлы дампа: C:\\Windows\\Minidump\\ 3. Анализ: WinDbg → !analyze -v 4. Частые причины: драйверы (обновить), RAM (memtest86), перегрев")

    kb.save()
    print(f"  system: {len(kb.entries)} знаний, {len(kb.sources)} источников, {len(kb.solutions)} решений")


def train_network():
    """Обучение модуля сети"""
    kb = KnowledgeBase("network")

    kb.add_source("Windows Networking", "https://learn.microsoft.com/en-us/windows-server/networking/", "Документация по сетям Windows")
    kb.add_source("Cloudflare Learning", "https://www.cloudflare.com/learning/", "Обучающие материалы по сетям и DNS")
    kb.add_source("HTTP MDN", "https://developer.mozilla.org/en-US/docs/Web/HTTP", "Справочник по HTTP")

    kb.add("Диагностика сети", "Порядок: 1. ping 127.0.0.1 (loopback) 2. ping шлюз (ipconfig → Default Gateway) 3. ping 8.8.8.8 (внешний IP) 4. ping google.com (DNS). Где упало — там проблема", ["диагностика", "ping", "проблемы сети"])
    kb.add("DNS", "Кэш DNS: ipconfig /displaydns. Очистка: ipconfig /flushdns. Смена DNS: netsh interface ip set dns 'Wi-Fi' static 8.8.8.8. Рекомендуемые: Cloudflare 1.1.1.1, Google 8.8.8.8, Quad9 9.9.9.9", ["dns", "домен", "разрешение имён"])
    kb.add("Wi-Fi диагностика", "netsh wlan show interfaces — текущее подключение и сигнал. netsh wlan show profiles — сохранённые сети. netsh wlan show profile name=SSID key=clear — показать пароль. WiFi отчёт: netsh wlan show wlanreport", ["wifi", "wi-fi", "беспроводная"])
    kb.add("Порты и файрвол", "Открытые порты: netstat -ano | findstr LISTENING. Файрвол: netsh advfirewall show allprofiles. Открыть порт: netsh advfirewall firewall add rule name='My Port' protocol=TCP dir=in localport=8080 action=allow", ["порт", "файрвол", "firewall"])
    kb.add("VPN", "Встроенный VPN Windows: Settings → Network → VPN. PowerShell: Add-VpnConnection. Проверка: ipconfig /all — виртуальный адаптер. Утечка DNS: nslookup google.com — должен отвечать VPN DNS", ["vpn", "туннель"])
    kb.add("Скорость сети", "PowerShell тест скорости: Measure-Command {Invoke-WebRequest https://speed.cloudflare.com/__down?bytes=10000000 -OutFile nul}. Или: curl -o /dev/null -w '%{speed_download}' URL", ["скорость", "bandwidth", "speed test"])
    kb.add("Сброс сети", "Полный сброс: 1. netsh winsock reset 2. netsh int ip reset 3. ipconfig /flushdns 4. ipconfig /release && ipconfig /renew 5. Перезагрузка. Помогает при странных сетевых проблемах", ["сброс", "reset", "не работает сеть"])
    kb.add("Proxy настройки", "Проверить: netsh winhttp show proxy. Установить: netsh winhttp set proxy proxy-server:port. Убрать: netsh winhttp reset proxy. Системный прокси: Settings → Network → Proxy", ["прокси", "proxy"])

    kb.add_solution("нет интернета", "1. ipconfig /release && ipconfig /renew 2. ipconfig /flushdns 3. netsh winsock reset 4. Проверить DNS: nslookup google.com 8.8.8.8 5. Перезагрузить роутер 6. Драйвер сетевой карты: devmgmt.msc")
    kb.add_solution("медленный интернет", "1. Проверить нагрузку: resmon → Network 2. Проверить другие устройства (проблема роутера?) 3. Сменить DNS на 1.1.1.1 4. Проверить фоновые загрузки: Delivery Optimization 5. Попробовать проводное подключение")
    kb.add_solution("DNS не разрешает имена", "1. ipconfig /flushdns 2. Попробовать другой DNS: nslookup google.com 1.1.1.1 3. Если через VPN — проверить DNS leak 4. Проверить файл hosts: C:\\Windows\\System32\\drivers\\etc\\hosts 5. netsh int ip reset")
    kb.add_solution("Wi-Fi постоянно отключается", "1. Драйвер: обновить или откатить 2. Электропитание: devmgmt.msc → Network Adapter → Properties → Power Management → снять 'Allow to turn off' 3. Wi-Fi Sense: отключить автоподключение к открытым сетям 4. Забыть сеть и подключиться заново")

    kb.save()
    print(f"  network: {len(kb.entries)} знаний, {len(kb.sources)} источников, {len(kb.solutions)} решений")


def train_watchdog():
    """Обучение модуля здоровья"""
    kb = KnowledgeBase("watchdog")

    kb.add_source("Windows Health", "https://learn.microsoft.com/en-us/windows/security/operating-system-security/system-security/", "Здоровье и безопасность Windows")
    kb.add_source("Event Log Docs", "https://learn.microsoft.com/en-us/windows/win32/eventlog/event-logging", "Журнал событий Windows")

    kb.add("Проверка целостности системы", "sfc /scannow — проверка системных файлов. DISM /Online /Cleanup-Image /CheckHealth — быстрая проверка. DISM /Online /Cleanup-Image /RestoreHealth — восстановление. Запускать от админа", ["sfc", "dism", "целостность"])
    kb.add("Журнал событий", "Event Viewer: eventvwr.msc. Критические ошибки: Get-EventLog -LogName System -EntryType Error -Newest 20. Приложения: Get-EventLog -LogName Application -EntryType Error -Newest 20", ["event log", "журнал", "ошибки"])
    kb.add("Здоровье диска", "SMART статус: wmic diskdrive get status,model. PowerShell: Get-PhysicalDisk | Select FriendlyName,HealthStatus,OperationalStatus. CrystalDiskInfo — детальный SMART", ["диск", "smart", "здоровье"])
    kb.add("Автоматическое обслуживание", "Windows Maintenance: автоочистка, дефрагментация, диагностика. Запуск вручную: MSchedExe.exe Start. Настройка: Control Panel → Security and Maintenance → Maintenance", ["обслуживание", "maintenance"])
    kb.add("Мониторинг ресурсов", "Встроенные: resmon (Resource Monitor), perfmon (Performance Monitor). Счётчики: typeperf '\\Processor(_Total)\\% Processor Time' — CPU в реальном времени", ["мониторинг", "ресурсы", "perfmon"])

    kb.add_solution("система нестабильна", "1. sfc /scannow + DISM /RestoreHealth 2. Проверить Event Viewer на критические ошибки 3. Проверить температуру (перегрев) 4. Проверить RAM: mdsched.exe (Windows Memory Diagnostic) 5. Проверить диск: chkdsk C: /f")
    kb.add_solution("место на диске заканчивается", "1. cleanmgr /d C (Очистка диска) 2. Удалить старые точки восстановления: vssadmin delete shadows /for=C: /oldest 3. Dism /Cleanup-Image /StartComponentCleanup 4. Найти большие файлы 5. Перенести данные на другой диск")

    kb.save()
    print(f"  watchdog: {len(kb.entries)} знаний, {len(kb.sources)} источников, {len(kb.solutions)} решений")


def train_designer():
    """Обучение модуля дизайнера"""
    kb = KnowledgeBase("designer")

    kb.add_source("Material Design", "https://m3.material.io/", "Гайдлайны Material Design от Google")
    kb.add_source("Apple HIG", "https://developer.apple.com/design/human-interface-guidelines/", "Human Interface Guidelines от Apple")
    kb.add_source("Tailwind CSS", "https://tailwindcss.com/docs", "Документация Tailwind CSS")
    kb.add_source("CSS MDN", "https://developer.mozilla.org/en-US/docs/Web/CSS", "Справочник CSS")

    kb.add("Правило 60-30-10", "Основной цвет — 60% (фон), вторичный — 30% (карточки, панели), акцент — 10% (кнопки, ссылки). Создаёт визуальную гармонию", ["цвет", "палитра", "баланс"], "Дизайн")
    kb.add("Контраст текста", "WCAG AA: контраст минимум 4.5:1 для текста, 3:1 для крупного. Белый текст на тёмном фоне (#0a0e17) — контраст ~18:1, отлично. Серый #94a3b8 на тёмном — ~7:1, достаточно", ["контраст", "доступность", "wcag"])
    kb.add("Типографика", "Системные шрифты: font-family: 'Segoe UI', system-ui, sans-serif. Размеры: 13px мелкий, 14px обычный, 16px основной, 18-22px заголовки. Line-height: 1.5 для текста, 1.2 для заголовков", ["шрифт", "типографика", "font"])
    kb.add("Отступы и сетка", "Base unit: 4px или 8px. Отступы: 8, 12, 16, 20, 24, 32px. Grid gap: 16px. Padding карточки: 20px. Border-radius: 8px кнопки, 12px карточки", ["сетка", "отступы", "spacing"])
    kb.add("Тёмная тема", "Не используй чистый чёрный (#000). Лучше: #0a0e17, #111827, #1e293b — слои темноты. Текст: не чисто белый, а #e0e6f0. Тени: более заметные чем в светлой теме", ["dark", "тёмная тема", "dark mode"])
    kb.add("Анимации", "Длительность: 150ms для hover, 200-300ms для переходов, 500ms для появления. Easing: ease-out для появления, ease-in для исчезновения. Не анимируй layout (width/height) — используй transform", ["анимация", "transition", "motion"])
    kb.add("Адаптивность", "Breakpoints: 640px (mobile), 768px (tablet), 1024px (desktop), 1280px (wide). Mobile-first: начинай с мобильного, расширяй через min-width. Минимальный tap target: 44x44px", ["адаптивный", "responsive", "mobile"])
    kb.add("SVG иконки", "Размер: 16px inline, 20-24px кнопки, 32-48px навигация. stroke-width: 1.5-2px. Используй currentColor для наследования цвета. viewBox всегда задавать", ["иконки", "svg", "icons"])

    kb.add_solution("текст плохо читается", "1. Увеличить контраст (минимум 4.5:1) 2. Увеличить font-size (минимум 14px) 3. Увеличить line-height (1.5) 4. Добавить letter-spacing: 0.02em для мелкого текста")
    kb.add_solution("интерфейс выглядит перегруженным", "1. Увеличить отступы (padding/margin) 2. Уменьшить количество цветов 3. Добавить пустое пространство 4. Группировать связанные элементы 5. Убрать ненужные границы")

    kb.save()
    print(f"  designer: {len(kb.entries)} знаний, {len(kb.sources)} источников, {len(kb.solutions)} решений")


def train_platform():
    """Обучение модуля кроссплатформенной интеграции"""
    kb = KnowledgeBase("platform")

    kb.add_source("POSIX Standard", "https://pubs.opengroup.org/onlinepubs/9699919799/", "Стандарт POSIX — общий API для Unix-систем")
    kb.add_source("WSL Docs", "https://learn.microsoft.com/en-us/windows/wsl/", "Windows Subsystem for Linux")
    kb.add_source("Homebrew", "https://docs.brew.sh/", "Пакетный менеджер macOS")

    kb.add("WSL — Linux внутри Windows", "Windows Subsystem for Linux: wsl --install. Позволяет запускать Linux-команды из Windows. wsl -d Ubuntu — запустить Ubuntu. Файлы Windows доступны в /mnt/c/", ["wsl", "linux", "windows"], "Microsoft Docs")
    kb.add("Docker — единая среда", "Docker работает одинаково на всех ОС. docker run -it ubuntu bash — запустить Ubuntu контейнер. Docker Desktop для Windows/macOS, docker-ce для Linux", ["docker", "контейнер", "кроссплатформенность"])
    kb.add("Менеджеры пакетов", "Windows: winget (встроенный), choco, scoop. macOS: brew (Homebrew). Linux: apt (Debian/Ubuntu), dnf (Fedora), pacman (Arch), nix (универсальный). Nix — единственный кроссплатформенный", ["пакеты", "установка", "менеджер"])
    kb.add("Пути файлов", "Windows: C:\\Users\\user (обратный слэш). Linux/macOS: /home/user (прямой слэш). Python pathlib — работает на всех. В Python используй os.path.join() или Path()", ["пути", "path", "слэш"])
    kb.add("Переменные окружения", "Windows: set VAR=value / $env:VAR='value'. Linux/macOS: export VAR=value. Просмотр: Windows: set / Linux: env. Python: os.environ", ["env", "переменные", "окружение"])
    kb.add("Права доступа", "Windows: ACL (icacls). Linux/macOS: chmod/chown (rwx). Пример: chmod 755 file = rwxr-xr-x. В Windows нет прямого аналога chmod", ["права", "permissions", "chmod"])
    kb.add("Совместимость скриптов", "Python — работает везде. Bash — Linux/macOS нативно, Windows через Git Bash/WSL. PowerShell — Windows нативно, Linux/macOS через pwsh. Node.js — везде", ["скрипты", "совместимость", "bash", "python"])

    kb.add_solution("скрипт не работает на другой ОС", "1. Проверить пути (слэши) 2. Проверить переводы строк (LF vs CRLF) 3. Проверить зависимости (пакеты) 4. Использовать кроссплатформенные инструменты (Python, Node) 5. Docker для полной изоляции")
    kb.add_solution("нужно запустить Linux-команду на Windows", "1. WSL: wsl ls -la 2. Git Bash: поставляется с Git for Windows 3. Cygwin: полная Unix-среда 4. Docker: docker run -it ubuntu 5. MSYS2: минимальная Unix-среда")

    kb.save()
    print(f"  platform: {len(kb.entries)} знаний, {len(kb.sources)} источников, {len(kb.solutions)} решений")


if __name__ == "__main__":
    print("Обучение модулей AI-OS...")
    print()
    train_files()
    train_processes()
    train_system()
    train_network()
    train_watchdog()
    train_designer()
    train_platform()
    print()
    print("Обучение завершено. Знания сохранены в ai-os/knowledge/")
