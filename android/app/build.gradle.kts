plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.revaks.longevity"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.revaks.longevity"
        minSdk = 26
        targetSdk = 35
        versionCode = 9
        versionName = "0.3.2"

        // Данные приложения (советы, расписание, MIND, книги) лежат в assets
        // и в сборку не перекомпилируются.
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            // Внутренняя раздача: подписываем релиз отладочным ключом, чтобы APK
            // можно было сразу установить. Перед публикацией в Google Play
            // замените на собственный keystore (см. README).
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        viewBinding = true
    }

    sourceSets {
        // Реальные данные (JSON из assets) доступны и JVM-тестам ядра,
        // чтобы проверять парсинг/поиск на настоящем корпусе.
        getByName("test").resources.srcDir("src/main/assets")
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.fragment:fragment-ktx:1.8.5")

    // Опциональная on-device нейросеть (LiteRT-LM, формат .litertlm — Gemma 4 E2B и др.).
    // Модель не входит в APK: файл (~2–3 ГБ) скачивают или импортируют в приложение отдельно.
    implementation("com.google.ai.edge.litertlm:litertlm-android:0.17.0")

    testImplementation("junit:junit:4.13.2")
    // Для JVM-тестов ядра: на Android org.json встроен, в локальных тестах его нет.
    testImplementation("org.json:json:20240303")
}
