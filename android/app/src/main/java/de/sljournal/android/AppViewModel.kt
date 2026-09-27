package de.sljournal.android

import android.app.Application
import android.os.Build
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import de.sljournal.android.data.DEFAULT_TYPES
import de.sljournal.android.data.JournalApi
import de.sljournal.android.data.Me
import de.sljournal.android.data.Session
import de.sljournal.android.data.SessionStore
import de.sljournal.android.data.UnauthorizedException
import de.sljournal.android.data.normalizeServer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.HttpUrl.Companion.toHttpUrl

/** Anmeldung, Serververbindung und ein Zähler, der Listen nach Änderungen neu laden lässt. */
class AppViewModel(application: Application) : AndroidViewModel(application) {
    private val store = SessionStore(application)

    private val _session = MutableStateFlow(store.load())
    val session: StateFlow<Session?> = _session.asStateFlow()

    private val _me = MutableStateFlow<Me?>(null)
    val me: StateFlow<Me?> = _me.asStateFlow()

    private val _revision = MutableStateFlow(0)
    /** Steigt nach jedem Speichern; Bildschirme laden dann ihre Daten neu. */
    val revision: StateFlow<Int> = _revision.asStateFlow()

    private val _notice = MutableStateFlow<String?>(null)
    val notice: StateFlow<String?> = _notice.asStateFlow()

    var api: JournalApi? = _session.value?.let { JournalApi(it.server.toHttpUrl(), it.token) }
        private set

    val lastServer: String get() = store.lastServer()

    val types: Map<String, String> get() = _me.value?.types ?: DEFAULT_TYPES

    init {
        refreshMe()
    }

    val defaultDeviceName: String
        get() = listOf(Build.MANUFACTURER.replaceFirstChar { it.uppercase() }, Build.MODEL)
            .distinct().joinToString(" ").trim().ifEmpty { "Android-Gerät" }

    suspend fun login(server: String, password: String, otp: String, device: String) {
        val url = normalizeServer(server)
        val result = JournalApi(url, null).login(password, otp.trim(), device.trim().ifEmpty { defaultDeviceName })
        val session = Session(url.toString().trimEnd('/'), result.token, result.device)
        store.save(session)
        api = JournalApi(url, result.token)
        _session.value = session
        refreshMe()
    }

    fun logout() {
        val current = api
        viewModelScope.launch { runCatching { current?.logout() } }
        endSession(null)
    }

    private fun endSession(message: String?) {
        store.clear()
        api = null
        _me.value = null
        _session.value = null
        _notice.value = message
    }

    fun refreshMe() {
        val current = api ?: return
        viewModelScope.launch {
            runCatching { current.me() }
                .onSuccess { _me.value = it }
                .onFailure { handle(it) }
        }
    }

    fun changed() {
        _revision.value += 1
        refreshMe()
    }

    /** Gemeinsame Fehlerbehandlung: abgelaufene Anmeldung führt zurück zum Login. */
    fun handle(error: Throwable): String {
        if (error is UnauthorizedException) endSession(error.message)
        return error.message ?: "Unbekannter Fehler"
    }

    fun consumeNotice() {
        _notice.value = null
    }
}
