package de.sljournal.android.ui.components

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import android.webkit.MimeTypeMap
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/** Eine auf dem Gerät gewählte Datei, die nach dem Speichern hochgeladen wird. */
data class PendingFile(val uri: Uri, val name: String, val mime: String, val size: Long)

private const val MAX_UPLOAD = 25L * 1024 * 1024

fun authority(context: Context) = context.packageName + ".files"

fun describe(context: Context, uri: Uri): PendingFile {
    var name = uri.lastPathSegment ?: "Anhang"
    var size = -1L
    context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { cursor ->
        if (cursor.moveToFirst()) {
            cursor.getString(0)?.let { name = it }
            if (!cursor.isNull(1)) size = cursor.getLong(1)
        }
    }
    val mime = context.contentResolver.getType(uri)
        ?: MimeTypeMap.getSingleton().getMimeTypeFromExtension(name.substringAfterLast('.', "").lowercase())
        ?: "application/octet-stream"
    return PendingFile(uri, name, mime, size)
}

suspend fun readFile(context: Context, file: PendingFile): ByteArray = withContext(Dispatchers.IO) {
    val stream = context.contentResolver.openInputStream(file.uri) ?: throw IllegalStateException("Die Datei ${file.name} ist nicht lesbar.")
    stream.use {
        val bytes = it.readNBytesCompat(MAX_UPLOAD + 1)
        if (bytes.size > MAX_UPLOAD) throw IllegalStateException("${file.name} ist größer als 25 MB.")
        bytes
    }
}

private fun java.io.InputStream.readNBytesCompat(limit: Long): ByteArray {
    val out = java.io.ByteArrayOutputStream()
    val buffer = ByteArray(64 * 1024)
    var total = 0L
    while (total < limit) {
        val read = read(buffer, 0, minOf(buffer.size.toLong(), limit - total).toInt())
        if (read < 0) break
        out.write(buffer, 0, read)
        total += read
    }
    return out.toByteArray()
}

/** Ziel für ein Kamerafoto im App-Cache. */
fun newPhotoUri(context: Context): Pair<Uri, String> {
    val dir = File(context.cacheDir, "camera").apply { mkdirs() }
    val name = "Foto-" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd-HHmmss")) + ".jpg"
    val file = File(dir, name)
    return FileProvider.getUriForFile(context, authority(context), file) to name
}

/**
 * Heruntergeladenen Anhang mit einer passenden App öffnen. Die Datei liegt nur
 * im Cache und wird beim nächsten Öffnen eines Anhangs überschrieben.
 */
suspend fun openAttachment(context: Context, name: String, mime: String, bytes: ByteArray): String? {
    val file = withContext(Dispatchers.IO) {
        val dir = File(context.cacheDir, "attachments").apply {
            mkdirs()
            listFiles()?.forEach { it.delete() }
        }
        File(dir, name.replace('/', '_').ifBlank { "Anhang" }).apply { writeBytes(bytes) }
    }
    val uri = FileProvider.getUriForFile(context, authority(context), file)
    val type = mime.takeIf { it.isNotBlank() && it != "application/octet-stream" }
        ?: MimeTypeMap.getSingleton().getMimeTypeFromExtension(name.substringAfterLast('.', "").lowercase())
        ?: "application/octet-stream"
    val intent = Intent(Intent.ACTION_VIEW).setDataAndType(uri, type).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
    return try {
        context.startActivity(Intent.createChooser(intent, name).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        null
    } catch (e: ActivityNotFoundException) {
        "Keine App zum Öffnen von $name gefunden."
    }
}
