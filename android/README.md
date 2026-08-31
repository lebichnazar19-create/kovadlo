# Ковадло — Android-застосунок (модуль 14)

Той самий веб-інтерфейс (`web/static/index.html`, модулі 3/5/9/11) і те
саме ядро (`kovadlo/`, `web/`) — запаковані в звичайний Android-застосунок
з іконкою, splash-екраном і офлайн-роботою. Жодного Termux чи браузера
на телефоні користувача не потрібно.

## Чому Kotlin + WebView + Chaquopy (варіант А), а не переписування ядра на Kotlin

- **Ядро (модулі 1-13) і 600+ тестів лишаються без змін.** Переписати
  фізичні/інженерні розрахунки на Kotlin означало б продублювати й
  заново перевірити всю логіку модулів 1-13 — величезний обсяг роботи
  з реальним ризиком розбіжностей із уже перевіреною Python-версією.
- **`web/server.py` + `web/static/index.html` уже є повним UI** (модулі
  3, 5, 9, 11) — лишається лише показати ту саму сторінку в `WebView`
  замість браузера, і виконати Python не в терміналі, а всередині
  застосунку (Chaquopy).
- Chaquopy офіційно підтримує локальний `http.server` без жодних
  третьосторонніх Python-пакетів — а `kovadlo`/`web` не мають жодної
  зовнішньої залежності (лише стандартна бібліотека), тож збірка не
  тягне pip-колеса під Android ABI — швидше й надійніше.
- Мінус (чесно): застосунок важчий за суто нативний Kotlin (вбудований
  Python-інтерпретер) і трохи повільніший на холодному старті (Chaquopy
  розпаковує стандартну бібліотеку Python у сховище застосунку при
  першому запуску). Для локального однокористувацького інструменту без
  реального часу (розрахунки — мілісекунди) це не критично.

## Структура

```
android/
  settings.gradle.kts       # репозиторії (google/mavenCentral/chaquo.com/maven)
  build.gradle.kts          # версії плаґінів (AGP 8.5.2, Kotlin 1.9.24, Chaquopy 17.0.0)
  gradle.properties
  pysrc/
    kovadlo -> ../../kovadlo   # символічне посилання — ядро "як є", без копій
    web -> ../../web           # символічне посилання — той самий веб-шар
  app/
    build.gradle.kts        # minSdk 26, targetSdk 34, python.srcDirs("../pysrc")
    src/main/
      AndroidManifest.xml
      kotlin/com/kovadlo/app/
        KovadloApp.kt        # Application: старт Chaquopy + web.server.create_server()
        MainActivity.kt      # WebView на весь екран + splash-екран
        ProjectFileBridge.kt # JS-міст: збереження/відкриття файлу проєкту (SAF)
      res/                   # іконка (adaptive, векторна), тема, splash, рядки
```

**`pysrc/kovadlo` і `pysrc/web` — символічні посилання**, не копії:
`kovadlo`/`web` підключені "як є", одне джерело правди для десктопної й
мобільної версії. На Windows для символічних посилань потрібно або
клонувати репозиторій з увімкненою підтримкою symlink
(`git config core.symlinks true` + права розробника/адміністратора),
або збирати на Linux/macOS/CI (workflow нижче збирає на Ubuntu-раннері
GitHub Actions — там питання не стоїть).

## Дозволи

Лише один: `WRITE_EXTERNAL_STORAGE` з `android:maxSdkVersion="28"`.

**Свідомо не заявлений на новіших версіях** — на Android 10+ (API 29+,
scoped storage) ця дозволка однаково не дає вільного доступу до
файлової системи, тож просити її "про всяк випадок" означало б
дозвіл, який нічого не вмикає. Замість цього збереження й відкриття
файлу проєкту на API 29+ іде через **Storage Access Framework**
(`ACTION_CREATE_DOCUMENT`/`ACTION_OPEN_DOCUMENT`, `ProjectFileBridge.kt`)
— системний діалог вибору файлу, який не потребує ЖОДНОГО дозволу
взагалі й працює однаково на всіх версіях. Дозвіл лишається тільки для
сумісності зі старими пристроями (Android 9 і нижче), де SAF ще не
покриває всі випадки так добре.

## Формат файлу проєкту

`.json`, будь-яка назва. Структура:

```json
{
  "format": "kovadlo-project-full",
  "version": 1,
  "server": { "...": "усе, що віддає /api/project/export (web/project_io.py): кімната, проводка, освітлення/вентиляція/тепло/пожежна безпека, дах і отвори" },
  "client": { "tiling_settings": { "...": "поля вкладки «Розгортка/плитка», якщо вона була відкрита при збереженні" } }
}
```

`server` — повний, точний round-trip (є тести:
`tests/test_project_io.py`, `tests/test_server_project.py`).
`client.tiling_settings` — найкраще зусилля (плитка на сервері не
зберігається як стан, лише рахується на льоту; якщо вкладку не було
відкрито в момент збереження, поле просто відсутнє).

## Збірка

### Що перевірено насправді (чесно) — і чому збірка на телефоні неможлива

У цій сесії (Termux + proot-distro Ubuntu, aarch64, на самому телефоні,
що на ньому й працює Claude Code) я реально:

1. Встановив JDK 17, Android SDK cmdline-tools + `platform-tools` +
   `platforms;android-34` + `build-tools;34.0.0`, Gradle 8.7, і навіть
   портативний Python 3.11 (для `buildPython` — системний тут 3.14,
   новіший за підтримувані Chaquopy) — **усе встановилося й
   запустилося без проблем**.
2. Реалізував і **наживо перевірив через HTTP** увесь новий код модуля
   14 (`web/project_io.py` + `/api/project/export`/`/api/project/import`)
   — повний round-trip стану підтверджено (603 тести проходять).
3. Написав повний проєкт (`android/`), виправив реальні помилки
   конфігурації Chaquopy-DSL за фактичними логами Gradle (не за
   здогадкою), і **дійшов до `./gradlew :app:assembleDebug`, яка
   виконала 29 задач** (Kotlin-компіляція, обробка ресурсів, пакування
   Python-коду через Chaquopy — усе це відпрацювало) і впала лише на
   останньому кроці — виклику `aapt2` (компілятор ресурсів Android):

   ```
   Cannot run program ".../aapt2-8.5.2-.../aapt2": error=2, No such file or directory
   ```

   Перевірив бінарник напряму (`readelf -h aapt2`): **`Machine: Advanced
   Micro Devices X86-64`** — тобто це x86_64-бінарник, а телефон, на
   якому я працюю, — **aarch64** (`uname -m` = `aarch64`). Перевірив
   maven-репозиторій Google для aapt2 аж до найновішої версії
   (9.3.2) — класифікатора `linux-aarch64`/`linux_aarch64` **не існує
   в жодній версії**, лише `linux` (x86_64), `osx`, `windows`.
   `/proc/sys/fs/binfmt_misc` у цьому proot-оточенні порожній (немає
   файлу `register`) — прозора емуляція через qemu теж недоступна без
   реального root на ядрі пристрою.

**Висновок, чесно й остаточно:** інструментарій (JDK, Android SDK,
Gradle, Chaquopy) у Termux/proot-distro на телефоні встановлюється й
працює, і сама збірка Kotlin+Python-частини Chaquopy теж працює. Але
**останній крок — компіляція ресурсів через `aapt2` — принципово
неможливий на aarch64-Linux хості**, бо Google офіційно не публікує
`aapt2` для цієї архітектури (лише x86_64 Linux, macOS, Windows) —
це не тимчасове обмеження цієї сесії, а структурне обмеження
офіційного Android-інструментарію, що стосується БУДЬ-ЯКОГО ARM64-
телефона з Termux/proot-distro, не лише цього. Додатково (другорядний
фактор) телефон під час роботи мав дуже мало вільної пам'яті (~150-200
МБ, доступно 8 ГБ підкачки майже повністю зайнятої іншими процесами) —
навіть якби aapt2 існував для aarch64, збірка була б повільною й
ризикованою через це. **Реальна альтернатива нижче — не "про всяк
випадок", а єдиний робочий шлях зібрати саме APK з цього проєкту.**

### Варіант 1 — у Termux (proot-distro Ubuntu) — **працює лише на x86_64-хості**

**На звичайному телефоні (процесор ARM, aarch64 — майже всі Android-
телефони) ця збірка ГАРАНТОВАНО впаде на кроці `aapt2`** — див. пояснення
вище: Google не публікує `aapt2` для linux-aarch64 в жодній версії.
Має сенс лише якщо Termux/proot-distro запущено на x86_64-пристрої
(напр. Android-x86 у віртуалці на ПК) — тоді кроки нижче ідентичні
звичайній збірці на Linux:

```bash
# 1. JDK 17
apt-get install -y openjdk-17-jdk-headless

# 2. Android SDK cmdline-tools
mkdir -p ~/android-sdk/cmdline-tools
curl -L -o /tmp/cmdline-tools.zip \
  https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip -q /tmp/cmdline-tools.zip -d ~/android-sdk/cmdline-tools_tmp
mkdir -p ~/android-sdk/cmdline-tools/latest
mv ~/android-sdk/cmdline-tools_tmp/cmdline-tools/* ~/android-sdk/cmdline-tools/latest/
export ANDROID_HOME=~/android-sdk
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
yes | sdkmanager --licenses
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"

# 3. local.properties (вказати SDK для Gradle)
echo "sdk.dir=$ANDROID_HOME" > android/local.properties

# 4. buildPython — окремий Python 3.11 для Gradle/Chaquopy (не обов'язково
#    системний!). Якщо в системі лише дуже нова версія (як тут — 3.14,
#    новіша за підтримувані Chaquopy), візьміть портативний білд:
curl -L -o /tmp/py311.tar.gz \
  "https://github.com/astral-sh/python-build-standalone/releases/latest/download/cpython-3.11.16+20260825-aarch64-unknown-linux-gnu-install_only_stripped.tar.gz"
mkdir -p ~/py311 && tar xzf /tmp/py311.tar.gz -C ~/py311 --strip-components=1
# і виправити шлях у android/app/build.gradle.kts (python.buildPython(...))
# на ~/py311/bin/python3, якщо він не /root/py311/bin/python3

# 5. Збірка (закрийте інші застосунки на телефоні перед цим — потрібно
#    вільної пам'яті, орієнтовно від 3-4 ГБ)
cd android
./gradlew :app:assembleDebug --stacktrace

# APK з'явиться тут:
#   android/app/build/outputs/apk/debug/app-debug.apk
# Перенести на телефон і встановити (потрібно дозволити встановлення
# з невідомих джерел) або adb install app-debug.apk
```

### Варіант 2 — GitHub Actions (надійніше, рекомендовано)

Готовий workflow: `.github/workflows/android-build.yml`. Досить
запушити зміни у гілку `main` (чи запустити вручну через "Run workflow"
на вкладці Actions) — збірка йде на звичайній машині GitHub без
обмежень пам'яті телефону, а готовий `.apk` можна скачати з артефактів
запуску (`kovadlo-debug-apk`).

### Варіант 3 — Android Studio на комп'ютері

Найпростіший спосіб, якщо є ПК: відкрити папку `android/` в Android
Studio (Giraffe чи новіша), синхронізувати Gradle, "Run" на
підключеному телефоні чи "Build > Build APK(s)".

## Підпис і публікація

Збірка вище — **debug**-варіант (самопідписаний debug-ключем,
підходить для встановлення на власний телефон). Для публікації
(Google Play чи розповсюдження поза ним) потрібен release-підпис —
`keytool`/`android.signingConfigs` — навмисно не налаштовано тут, бо
це вимагає особистого ключа підпису розробника, який не можна
згенерувати "типовим".
