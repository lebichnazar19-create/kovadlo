plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.kovadlo.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.kovadlo.app"
        // 26 (Android 8.0), а не 21/24: adaptive-icon (mipmap-anydpi-v26) —
        // єдиний ресурс іконки в цьому проєкті, без растрового fallback
        // для старіших версій. На 2026 рік частка Android <8.0 серед
        // активних пристроїв мізерна — свідомий компроміс, щоб не
        // генерувати бінарні PNG вручну лише заради формального minSdk 21.
        // (Chaquopy 17 вимагає мінімум 24 — 26 із запасом проходить і це.)
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        ndk {
            // Обмежуємось однією архітектурою (більшість сучасних
            // телефонів) — менше часу й місця на першу збірку. Додайте
            // "x86_64" за потреби (емулятор), "armeabi-v7a" для зовсім
            // старих пристроїв (Python ≤ 3.11 — саме наша версія).
            abiFilters += listOf("arm64-v8a")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        buildConfig = true
    }
}

// Налаштування Chaquopy — ОКРЕМИЙ верхньорівневий блок (не всередині
// android{}!) починаючи з Chaquopy 17 (стара вкладена в
// android.defaultConfig.python{} форма — deprecated, лише для Groovy
// build.gradle й старіших версій плаґіна). Джерело:
// https://chaquo.com/chaquopy/doc/current/android.html#chaquopy-block
chaquopy {
    defaultConfig {
        // Версія Python НА ТЕЛЕФОНІ — має збігатися мажор.мінор з buildPython.
        version = "3.11"

        // Python-збирач НА МАШИНІ ЗБІРКИ (не на телефоні користувача) —
        // потрібен лише під час компіляції для запуску pip/compileall.
        // Пакетів через pip тут немає (kovadlo/web — чистий stdlib), тож
        // це просто відповідний по мажор.мінор інтерпретатор на диску.
        // Два виклики buildPython() — це впорядкований список кандидатів
        // (Chaquopy пробує кожен по черзі, перший знайдений і використає):
        // перший шлях — для цієї машини, другий — "python3.11" з PATH,
        // який знаходить CI (там ставимо через actions/setup-python).
        buildPython("/root/py311/bin/python3")
        buildPython("python3.11")
    }

    sourceSets {
        getByName("main") {
            // Ядро kovadlo/ і web/ підключені ЯК Є через символічні
            // посилання в ../pysrc — жодного копіювання чи переписування
            // (обмеження модуля 14: ядро й web-шар не чіпати).
            srcDir("../pysrc")
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.activity:activity-ktx:1.9.1")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.core:core-splashscreen:1.0.1")
}
