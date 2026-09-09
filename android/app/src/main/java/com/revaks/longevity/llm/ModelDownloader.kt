package com.revaks.longevity.llm

import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/** Скачивание модели в фоне с прогрессом. */
object ModelDownloader {

    fun start(
        url: String,
        target: File,
        onProgress: (bytesDone: Long, total: Long) -> Unit,
        onDone: (Result<File>) -> Unit,
    ) {
        thread(isDaemon = true, name = "llm-download") {
            val result = runCatching {
                target.parentFile?.mkdirs()
                val tmp = File(target.parentFile, target.name + ".part")
                val connection = URL(url).openConnection() as HttpURLConnection
                connection.connectTimeout = 15_000
                connection.readTimeout = 30_000
                connection.instanceFollowRedirects = true
                val total = connection.contentLengthLong.coerceAtLeast(0L)
                connection.inputStream.use { input ->
                    tmp.outputStream().use { output ->
                        val buffer = ByteArray(64 * 1024)
                        var done = 0L
                        while (true) {
                            val read = input.read(buffer)
                            if (read < 0) break
                            output.write(buffer, 0, read)
                            done += read
                            onProgress(done, total)
                        }
                    }
                }
                if (!tmp.renameTo(target)) {
                    tmp.copyTo(target, overwrite = true)
                    tmp.delete()
                }
                target
            }
            onDone(result)
        }
    }
}
