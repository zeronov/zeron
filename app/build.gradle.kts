plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.zeronboost.android"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.zeronboost.android"
        minSdk = 26
        targetSdk = 33
        versionCode = 6
        versionName = "0.6.0"
    }
    signingConfigs {
        // Fixed key (committed on purpose, personal tool): every build is signed the same,
        // so a new version installs OVER the old one without uninstalling.
        getByName("debug") {
            storeFile = file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
            storeType = "pkcs12"
        }
    }
    buildTypes {
        release { isMinifyEnabled = false }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}
