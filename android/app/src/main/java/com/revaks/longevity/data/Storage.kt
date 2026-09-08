package com.revaks.longevity.data

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONObject
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit

/** Запись дневника — аналог строки таблицы diary в longevity/storage.py. */
data class DiaryEntry(
    val id: Long,
    val date: String,
    val created: String,
    val text: String,
)

class StorageError(message: String) : Exception(message)

/**
 * Хранилище заметок, отметок выполнения и настроек — порт longevity/storage.py.
 *
 * Мобильная версия стартует с чистой базой (таблица legacy-заметок `notes`
 * и перенос notes.json десктопу не нужны), поэтому схема — это дневник,
 * отметки, профиль и meta.
 */
class Storage(context: Context) : SQLiteOpenHelper(context, DB_NAME, null, DB_VERSION) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            "CREATE TABLE IF NOT EXISTS diary (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "date TEXT NOT NULL, " +
                "created TEXT NOT NULL, " +
                "text TEXT NOT NULL)"
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_diary_date ON diary(date)")
        db.execSQL(
            "CREATE TABLE IF NOT EXISTS completions (" +
                "date TEXT NOT NULL, " +
                "item_id TEXT NOT NULL, " +
                "done_at TEXT NOT NULL, " +
                "PRIMARY KEY (date, item_id))"
        )
        db.execSQL(
            "CREATE TABLE IF NOT EXISTS profile (" +
                "key TEXT PRIMARY KEY, " +
                "value TEXT NOT NULL)"
        )
        db.execSQL(
            "CREATE TABLE IF NOT EXISTS meta (" +
                "key TEXT PRIMARY KEY, " +
                "value TEXT NOT NULL)"
        )
        insertMeta(db, SCHEMA_VERSION_KEY, SCHEMA_VERSION)
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        // Версия 1 — первая; будущие миграции добавляются здесь.
    }

    override fun onOpen(db: SQLiteDatabase) {
        super.onOpen(db)
        checkSchemaVersion(db)
    }

    private fun checkSchemaVersion(db: SQLiteDatabase) {
        val found = getMetaFrom(db, SCHEMA_VERSION_KEY)
        val v = found?.toIntOrNull()
            ?: throw StorageError("База данных помечена неизвестной версией схемы ($found). Возможно, файл повреждён.")
        if (v > SCHEMA_VERSION.toInt()) {
            throw StorageError(
                "База данных создана более новой версией приложения (схема $v, " +
                    "эта версия знает $SCHEMA_VERSION). Обновите «Ассистент долголетия»."
            )
        }
    }

    // ------------------------------------------------------------------ дневник

    private fun rowToEntry(cursor: android.database.Cursor): DiaryEntry = DiaryEntry(
        id = cursor.getLong(cursor.getColumnIndexOrThrow("id")),
        date = cursor.getString(cursor.getColumnIndexOrThrow("date")),
        created = cursor.getString(cursor.getColumnIndexOrThrow("created")),
        text = cursor.getString(cursor.getColumnIndexOrThrow("text")),
    )

    /** Все заметки дня, по времени создания. */
    fun diaryEntriesOn(date: String): List<DiaryEntry> {
        val db = readableDatabase
        return db.query(
            "diary", null, "date = ?", arrayOf(date),
            null, null, "created, id"
        ).use { c ->
            buildList {
                while (c.moveToNext()) add(rowToEntry(c))
            }
        }
    }

    fun diaryEntriesInRange(start: String, end: String): List<DiaryEntry> {
        val db = readableDatabase
        return db.query(
            "diary", null, "date BETWEEN ? AND ?", arrayOf(start, end),
            null, null, "date, created, id"
        ).use { c ->
            buildList {
                while (c.moveToNext()) add(rowToEntry(c))
            }
        }
    }

    fun hasDiaryNotes(date: String): Boolean {
        val db = readableDatabase
        db.query("diary", arrayOf("1"), "date = ?", arrayOf(date), null, null, null, "1")
            .use { return it.moveToFirst() }
    }

    /** Новая заметка на день; возвращает id записи (0, если текст пуст). */
    fun addDiary(date: String, text: String): Long {
        val clean = text.trim()
        if (clean.isEmpty()) return 0L
        val values = ContentValues().apply {
            put("date", date)
            put("created", nowUtc())
            put("text", clean)
        }
        return writableDatabase.insert("diary", null, values)
    }

    fun updateDiary(entryId: Long, text: String): Boolean {
        val clean = text.trim()
        if (clean.isEmpty()) return false
        val values = ContentValues().apply { put("text", clean) }
        return writableDatabase.update("diary", values, "id = ?", arrayOf(entryId.toString())) > 0
    }

    fun deleteDiary(entryId: Long): Boolean =
        writableDatabase.delete("diary", "id = ?", arrayOf(entryId.toString())) > 0

    // ------------------------------------------------------------------ отметки

    /** Переключить отметку; возвращает новое состояние (true = выполнено). */
    fun toggleCompletion(date: String, itemId: String): Boolean {
        val db = writableDatabase
        db.beginTransaction()
        return try {
            val deleted = db.delete(
                "completions", "date = ? AND item_id = ?", arrayOf(date, itemId)
            )
            if (deleted > 0) {
                db.setTransactionSuccessful()
                false
            } else {
                db.insert(
                    "completions", null,
                    ContentValues().apply {
                        put("date", date)
                        put("item_id", itemId)
                        put("done_at", nowUtc())
                    }
                )
                db.setTransactionSuccessful()
                true
            }
        } finally {
            db.endTransaction()
        }
    }

    fun completionsOn(date: String): Set<String> {
        val db = readableDatabase
        return db.query(
            "completions", arrayOf("item_id"), "date = ?", arrayOf(date),
            null, null, null
        ).use { c ->
            buildSet {
                while (c.moveToNext()) add(c.getString(0))
            }
        }
    }

    /** Сколько дней за период отмечен каждый пункт (item_id -> счётчик). */
    fun completionCountsInRange(start: String, end: String): Map<String, Int> {
        val db = readableDatabase
        val result = HashMap<String, Int>()
        db.rawQuery(
            "SELECT item_id, COUNT(*) AS n FROM completions " +
                "WHERE date BETWEEN ? AND ? GROUP BY item_id",
            arrayOf(start, end)
        ).use { c ->
            while (c.moveToNext()) result[c.getString(0)] = c.getInt(1)
        }
        return result
    }

    // ------------------------------------------------------------------ настройки

    /** Значение настройки любого JSON-типа; испорченное значение — как отсутствующее. */
    fun getValue(key: String, default: Any? = null): Any? {
        checkPrefix(key)
        val db = readableDatabase
        val value = db.query(
            "profile", arrayOf("value"), "key = ?", arrayOf(key), null, null, null
        ).use { c -> if (c.moveToFirst()) c.getString(0) else null }
            ?: return default
        return try {
            JSONObject(value).opt("v")
        } catch (e: Exception) {
            default
        }
    }

    /** Сохранить значение любого JSON-совместимого типа. */
    fun setValue(key: String, value: Any?) {
        checkPrefix(key)
        val wrapped = JSONObject().put("v", value ?: JSONObject.NULL).toString()
        val db = writableDatabase
        val values = ContentValues().apply {
            put("key", key)
            put("value", wrapped)
        }
        db.insertWithOnConflict("profile", null, values, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun getMeta(key: String): String? {
        val db = readableDatabase
        return db.query(
            "meta", arrayOf("value"), "key = ?", arrayOf(key), null, null, null
        ).use { c -> if (c.moveToFirst()) c.getString(0) else null }
    }

    fun setMeta(key: String, value: String) {
        val db = writableDatabase
        db.insertWithOnConflict(
            "meta", null,
            ContentValues().apply {
                put("key", key)
                put("value", value)
            },
            SQLiteDatabase.CONFLICT_REPLACE
        )
    }

    private fun getMetaFrom(db: SQLiteDatabase, key: String): String? {
        return db.query(
            "meta", arrayOf("value"), "key = ?", arrayOf(key), null, null, null
        ).use { c -> if (c.moveToFirst()) c.getString(0) else null }
    }

    private fun insertMeta(db: SQLiteDatabase, key: String, value: String) {
        db.insertWithOnConflict(
            "meta", null,
            ContentValues().apply {
                put("key", key)
                put("value", value)
            },
            SQLiteDatabase.CONFLICT_IGNORE
        )
    }

    private fun checkPrefix(key: String) {
        if (!key.startsWith(APP_PREFIX) && !key.startsWith(USER_PREFIX)) {
            throw IllegalArgumentException(
                "ключ '$key' должен начинаться с '$APP_PREFIX' или '$USER_PREFIX'"
            )
        }
    }

    private fun nowUtc(): String =
        OffsetDateTime.now(ZoneOffset.UTC).truncatedTo(ChronoUnit.SECONDS).toString()

    companion object {
        private const val DB_NAME = "data.db"
        private const val DB_VERSION = 1
        private const val SCHEMA_VERSION = "1"
        private const val SCHEMA_VERSION_KEY = "schema_version"

        /** Префикс для ключей настроек приложения. */
        const val APP_PREFIX = "app."

        /** Префикс для ключей профиля пользователя. */
        const val USER_PREFIX = "user."
    }
}
