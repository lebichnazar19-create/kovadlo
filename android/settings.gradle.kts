pluginManagement {
    repositories {
        gradlePluginPortal()
        google()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // Тут лежить сама Python-збірка для Android (таргет-дистрибутив),
        // яку тягне плаґін Chaquopy під час білду — без цього репозиторію
        // ЗБІРКА НЕ ПРОЙДЕ, навіть якщо сам плаґін уже знайдено на
        // Gradle Plugin Portal.
        maven(url = "https://chaquo.com/maven")
    }
}

rootProject.name = "Kovadlo"
include(":app")
