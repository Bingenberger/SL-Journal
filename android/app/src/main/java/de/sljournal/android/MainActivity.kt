package de.sljournal.android

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import de.sljournal.android.ui.JournalRoot
import de.sljournal.android.ui.editor.EditorRequest
import de.sljournal.android.ui.theme.JournalTheme

class MainActivity : ComponentActivity() {
    private val app: AppViewModel by viewModels()
    private var shared by mutableStateOf<EditorRequest?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (savedInstanceState == null) shared = sharedContent(intent)
        setContent {
            JournalTheme {
                JournalRoot(app, shared, onSharedConsumed = { shared = null })
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        sharedContent(intent)?.let { shared = it }
    }

    /** Text, Links, Fotos oder Dateien, die aus einer anderen App geteilt wurden. */
    private fun sharedContent(intent: Intent?): EditorRequest? {
        if (intent == null) return null
        val uris: List<Uri> = when (intent.action) {
            Intent.ACTION_SEND -> listOfNotNull(stream(intent))
            Intent.ACTION_SEND_MULTIPLE -> streams(intent)
            else -> return null
        }
        val text = intent.getStringExtra(Intent.EXTRA_TEXT).orEmpty().trim()
        val subject = intent.getStringExtra(Intent.EXTRA_SUBJECT).orEmpty().trim()
        if (text.isEmpty() && uris.isEmpty()) return null
        val title = subject.ifEmpty { text.lineSequence().firstOrNull { it.isNotBlank() }?.take(120).orEmpty() }
        return EditorRequest(type = "note", title = title, body = text, files = uris)
    }

    @Suppress("DEPRECATION")
    private fun stream(intent: Intent): Uri? =
        if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        else intent.getParcelableExtra(Intent.EXTRA_STREAM)

    @Suppress("DEPRECATION")
    private fun streams(intent: Intent): List<Uri> =
        (if (Build.VERSION.SDK_INT >= 33) intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
        else intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM)).orEmpty()
}
