package de.sljournal.android.ui.voice

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.Pause
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material.icons.outlined.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.LargeFloatingActionButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import de.sljournal.android.AppViewModel

private fun clock(seconds: Int) = "%02d:%02d".format(seconds / 60, seconds % 60)

/**
 * Sprachi wie im Browser: aufnehmen, anhören, im Tagesjournal speichern.
 * Die Aufnahme wird als Journaleintrag von jetzt mit Audioanhang abgelegt.
 */
@Composable
fun VoiceDialog(app: AppViewModel, onDismiss: () -> Unit, onSaved: (entryId: Int) -> Unit) {
    val recorder: VoiceRecorder = viewModel()
    val state by recorder.state.collectAsState()
    val error by recorder.error.collectAsState()
    val context = LocalContext.current
    var confirmDiscard by remember { mutableStateOf(false) }

    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) recorder.start()
        else recorder.reportError("Der Mikrofonzugriff wurde nicht erlaubt. Bitte in den Android-Einstellungen für SL-Journal freigeben.")
    }

    fun record() {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) recorder.start()
        else permission.launch(Manifest.permission.RECORD_AUDIO)
    }

    fun close() {
        when (state) {
            is VoiceState.Saving -> Unit
            is VoiceState.Idle -> { recorder.discard(); onDismiss() }
            else -> confirmDiscard = true
        }
    }

    AlertDialog(
        onDismissRequest = { close() },
        icon = { Icon(Icons.Outlined.Mic, null) },
        title = { Text("Sprachi") },
        text = {
            Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                val status = when (val s = state) {
                    VoiceState.Idle -> "Bereit zur Aufnahme."
                    is VoiceState.Recording -> "Aufnahme läuft …"
                    is VoiceState.Recorded -> if (s.playing) "Wiedergabe …" else "Aufnahme fertig. Anhören oder im Tagesjournal speichern."
                    VoiceState.Saving -> "Aufnahme wird gespeichert …"
                }
                Text(status, textAlign = TextAlign.Center, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                val seconds = when (val s = state) {
                    is VoiceState.Recording -> s.seconds
                    is VoiceState.Recorded -> s.seconds
                    else -> 0
                }
                Text(
                    clock(seconds),
                    fontFamily = FontFamily.Monospace, fontSize = 40.sp,
                    color = if (state is VoiceState.Recording) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.semantics { contentDescription = "Aufnahmedauer ${seconds / 60} Minuten ${seconds % 60} Sekunden" },
                )
                if (state is VoiceState.Recording) {
                    LinearProgressIndicator(
                        progress = { seconds / VoiceRecorder.MAX_SECONDS.toFloat() },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Text("Höchstens ${VoiceRecorder.MAX_SECONDS / 60} Minuten", style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.height(4.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    when (val s = state) {
                        is VoiceState.Recording -> LargeFloatingActionButton(
                            onClick = { recorder.stop() },
                            containerColor = MaterialTheme.colorScheme.errorContainer,
                        ) { Icon(Icons.Outlined.Stop, "Aufnahme stoppen", Modifier.size(36.dp)) }
                        is VoiceState.Recorded -> {
                            FilledTonalIconButton(onClick = { recorder.togglePlayback() }, modifier = Modifier.size(56.dp)) {
                                Icon(if (s.playing) Icons.Outlined.Pause else Icons.Outlined.PlayArrow, if (s.playing) "Anhalten" else "Anhören")
                            }
                            OutlinedButton(onClick = { record() }) { Icon(Icons.Outlined.Mic, null); Text(" Neu aufnehmen") }
                        }
                        VoiceState.Saving -> CircularProgressIndicator()
                        VoiceState.Idle -> LargeFloatingActionButton(onClick = { record() }) {
                            Icon(Icons.Outlined.Mic, "Aufnahme starten", Modifier.size(36.dp))
                        }
                    }
                }
                if (error != null) {
                    Text(error!!, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center)
                }
            }
        },
        confirmButton = {
            Button(
                enabled = state is VoiceState.Recorded,
                onClick = {
                    recorder.save { bytes ->
                        // app.handle meldet bei abgelaufenem Token ab und liefert die Meldung.
                        val entry = runCatching { app.api!!.voice(bytes) }.getOrElse { throw Exception(app.handle(it)) }
                        app.changed()
                        onSaved(entry.id)
                    }
                },
            ) { Text("Im Tagesjournal speichern") }
        },
        dismissButton = {
            TextButton(onClick = { close() }, enabled = state !is VoiceState.Saving) { Text("Abbrechen") }
        },
    )

    if (confirmDiscard) {
        AlertDialog(
            onDismissRequest = { confirmDiscard = false },
            title = { Text("Aufnahme verwerfen?") },
            text = { Text("Die Sprachi ist noch nicht gespeichert.") },
            confirmButton = { TextButton(onClick = { confirmDiscard = false; recorder.discard(); onDismiss() }) { Text("Verwerfen") } },
            dismissButton = { TextButton(onClick = { confirmDiscard = false }) { Text("Weiter") } },
        )
    }
}
