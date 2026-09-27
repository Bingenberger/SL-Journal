package de.sljournal.android.ui.voice

import android.app.Application
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.os.Build
import android.os.SystemClock
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/** Zustand der Sprachi-Aufnahme. */
sealed interface VoiceState {
    data object Idle : VoiceState
    data class Recording(val seconds: Int) : VoiceState
    data class Recorded(val seconds: Int, val playing: Boolean = false) : VoiceState
    data object Saving : VoiceState
}

/**
 * Nimmt Sprachis als AAC in MP4 (audio/mp4, .m4a) auf – ein Format, das der
 * Server wie die Browseraufnahmen annimmt. Wie im Browser höchstens zehn
 * Minuten und knapp 25 MB. Liegt im ViewModel, damit eine Drehung des Geräts
 * die laufende Aufnahme nicht abbricht.
 */
class VoiceRecorder(application: Application) : AndroidViewModel(application) {
    private val _state = MutableStateFlow<VoiceState>(VoiceState.Idle)
    val state: StateFlow<VoiceState> = _state.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private var recorder: MediaRecorder? = null
    private var player: MediaPlayer? = null
    private var ticker: Job? = null
    private var started = 0L
    private var limitReached = false

    private val file: File
        get() = File(getApplication<Application>().cacheDir, "voice").apply { mkdirs() }.resolve("sprachi.m4a")

    val hasRecording: Boolean get() = _state.value is VoiceState.Recorded || _state.value is VoiceState.Recording

    fun start() {
        discard()
        _error.value = null
        @Suppress("DEPRECATION")
        val next = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(getApplication()) else MediaRecorder()
        try {
            next.apply {
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                setAudioChannels(1)
                setAudioSamplingRate(44_100)
                setAudioEncodingBitRate(96_000)
                setMaxDuration(MAX_SECONDS * 1000)
                setMaxFileSize(MAX_BYTES)
                setOnInfoListener { _, what, _ ->
                    if (what == MediaRecorder.MEDIA_RECORDER_INFO_MAX_DURATION_REACHED ||
                        what == MediaRecorder.MEDIA_RECORDER_INFO_MAX_FILESIZE_REACHED
                    ) {
                        limitReached = true
                        stop()
                    }
                }
                setOutputFile(file.absolutePath)
                prepare()
                start()
            }
        } catch (e: Exception) {
            next.release()
            _error.value = "Die Aufnahme konnte nicht gestartet werden. Wird das Mikrofon gerade von einer anderen App genutzt?"
            return
        }
        recorder = next
        limitReached = false
        started = SystemClock.elapsedRealtime()
        _state.value = VoiceState.Recording(0)
        ticker = viewModelScope.launch {
            while (isActive) {
                _state.value = VoiceState.Recording(elapsed())
                delay(250)
            }
        }
    }

    private fun elapsed() = ((SystemClock.elapsedRealtime() - started) / 1000).toInt()

    fun stop() {
        val current = recorder ?: return
        ticker?.cancel()
        val seconds = elapsed()
        recorder = null
        // Nach Erreichen der Grenze hat der Recorder schon selbst angehalten;
        // ein Fehler beim Stoppen bedeutet dann keine verlorene Aufnahme.
        val ok = runCatching { current.stop() }.isSuccess || limitReached
        current.release()
        if (!ok || !file.exists() || file.length() == 0L) {
            file.delete()
            _state.value = VoiceState.Idle
            _error.value = "Keine Audiodaten aufgenommen. Bitte erneut versuchen."
        } else {
            _state.value = VoiceState.Recorded(seconds)
        }
    }

    fun togglePlayback() {
        val recorded = _state.value as? VoiceState.Recorded ?: return
        player?.let {
            it.release()
            player = null
            _state.value = recorded.copy(playing = false)
            return
        }
        player = runCatching {
            MediaPlayer().apply {
                setDataSource(file.absolutePath)
                setOnCompletionListener { stopPlayback() }
                prepare()
                start()
            }
        }.getOrElse {
            _error.value = "Die Aufnahme lässt sich nicht abspielen."
            null
        }
        if (player != null) _state.value = recorded.copy(playing = true)
    }

    private fun stopPlayback() {
        player?.release()
        player = null
        (_state.value as? VoiceState.Recorded)?.let { _state.value = it.copy(playing = false) }
    }

    /** Übergibt die Aufnahme zum Speichern; bei Erfolg wird sie verworfen. */
    fun save(upload: suspend (ByteArray) -> Unit) {
        val recorded = _state.value as? VoiceState.Recorded ?: return
        stopPlayback()
        _state.value = VoiceState.Saving
        _error.value = null
        viewModelScope.launch {
            try {
                upload(withContext(Dispatchers.IO) { file.readBytes() })
                discard()
            } catch (e: Exception) {
                _state.value = recorded.copy(playing = false)
                _error.value = (e.message ?: "Speichern fehlgeschlagen.") + " Die Aufnahme bleibt für einen neuen Versuch erhalten."
            }
        }
    }

    fun discard() {
        ticker?.cancel()
        recorder?.let { runCatching { it.stop() }; it.release() }
        recorder = null
        stopPlayback()
        file.delete()
        _state.value = VoiceState.Idle
        _error.value = null
    }

    fun reportError(message: String) {
        _error.value = message
    }

    override fun onCleared() {
        discard()
    }

    companion object {
        const val MAX_SECONDS = 600
        const val MAX_BYTES = 24L * 1024 * 1024
    }
}
