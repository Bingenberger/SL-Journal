package de.sljournal.android.ui.components

import android.content.Context
import android.media.MediaPlayer
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/** Formate, die auch der Browser als Sprachi abspielt. */
fun isAudio(mime: String) = mime in setOf("audio/webm", "audio/ogg", "audio/mp4")

/**
 * Spielt Audioanhänge (Sprachis) direkt in der Eintragsansicht ab. Die
 * entschlüsselte Datei liegt nur während der Wiedergabe im App-Cache.
 */
class AttachmentPlayer(private val context: Context) {
    var playingId by mutableStateOf<Int?>(null)
        private set
    var loadingId by mutableStateOf<Int?>(null)
        private set
    private var player: MediaPlayer? = null
    private var file: File? = null

    suspend fun toggle(id: Int, mime: String, load: suspend () -> ByteArray) {
        if (playingId == id) {
            stop()
            return
        }
        stop()
        loadingId = id
        try {
            val bytes = load()
            val target = withContext(Dispatchers.IO) {
                val ext = when (mime) { "audio/webm" -> "webm"; "audio/ogg" -> "ogg"; else -> "m4a" }
                File(context.cacheDir, "audio").apply { mkdirs() }.resolve("wiedergabe.$ext").apply { writeBytes(bytes) }
            }
            file = target
            player = MediaPlayer().apply {
                setDataSource(target.absolutePath)
                setOnCompletionListener { stop() }
                prepare()
                start()
            }
            playingId = id
        } catch (e: Exception) {
            stop()
            throw e
        } finally {
            loadingId = null
        }
    }

    fun stop() {
        player?.release()
        player = null
        file?.delete()
        file = null
        playingId = null
    }
}

@Composable
fun rememberAttachmentPlayer(): AttachmentPlayer {
    val context = LocalContext.current.applicationContext
    val player = remember { AttachmentPlayer(context) }
    DisposableEffect(player) { onDispose { player.stop() } }
    return player
}
