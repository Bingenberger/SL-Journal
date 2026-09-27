package de.sljournal.android.ui.editor

import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.AttachFile
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.PhotoCamera
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import de.sljournal.android.AppViewModel
import de.sljournal.android.data.Entry
import de.sljournal.android.data.EntryDraft
import de.sljournal.android.data.Item
import de.sljournal.android.data.NewTask
import de.sljournal.android.ui.components.DateButton
import de.sljournal.android.ui.components.PendingFile
import de.sljournal.android.ui.components.TimeButton
import de.sljournal.android.ui.components.describe
import de.sljournal.android.ui.components.formatSize
import de.sljournal.android.ui.components.newPhotoUri
import de.sljournal.android.ui.components.readFile
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter

/** Was der Editor bearbeiten soll: einen neuen Eintrag (mit Vorgaben) oder einen vorhandenen. */
data class EditorRequest(
    val existing: Entry? = null,
    val date: String? = null,
    val type: String = "note",
    // Aus „Teilen“ in einer anderen App:
    val title: String = "",
    val body: String = "",
    val files: List<Uri> = emptyList(),
)

private class TaskLine(text: String = "", due: String? = null) {
    var text by mutableStateOf(text)
    var due by mutableStateOf(due)
}

/**
 * Eintragsformular. Telefon: alles untereinander. Tablet: Text links,
 * Datum, Beteiligte, Zuordnungen, Aufgaben und Anhänge rechts daneben.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun EntryEditor(app: AppViewModel, request: EditorRequest, onClose: () -> Unit, onSaved: (Entry) -> Unit) {
    val existing = request.existing
    val now = remember { LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm")) }
    val today = remember { LocalDate.now().toString() }
    var type by remember { mutableStateOf(existing?.type ?: request.type) }
    var date by remember { mutableStateOf(existing?.date ?: request.date ?: today) }
    var time by remember { mutableStateOf(existing?.time ?: if ((request.date ?: today) == today) now else "") }
    var title by remember { mutableStateOf(existing?.title ?: request.title) }
    var body by remember { mutableStateOf(existing?.body ?: request.body) }
    var agenda by remember { mutableStateOf(existing?.agenda ?: "") }
    var decisions by remember { mutableStateOf(existing?.decisions ?: "") }
    var sender by remember { mutableStateOf(existing?.sender ?: "") }
    var recipients by remember { mutableStateOf(existing?.recipients ?: "") }
    var participants by remember { mutableStateOf(existing?.participantItems ?: emptyList()) }
    var projects by remember { mutableStateOf(existing?.projectItems ?: emptyList()) }
    var cases by remember { mutableStateOf(existing?.caseItems ?: emptyList()) }
    var tags by remember { mutableStateOf(existing?.tags?.map { Item(kind = "tag", label = it) } ?: emptyList()) }
    val tasks = remember { mutableStateListOf<TaskLine>() }
    val context = LocalContext.current
    val files = remember {
        mutableStateListOf<PendingFile>().apply {
            request.files.forEach { uri -> runCatching { describe(context, uri) }.onSuccess { add(it) } }
        }
    }
    var busy by remember { mutableStateOf(false) }
    // Nach dem ersten erfolgreichen Speichern gesetzt, damit ein erneuter
    // Versuch (etwa nach einem fehlgeschlagenen Upload) keinen zweiten Eintrag anlegt.
    var savedId by remember { mutableStateOf(existing?.id) }
    var error by remember { mutableStateOf<String?>(null) }
    var confirmClose by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    val dirty = title != (existing?.title ?: "") || body != (existing?.body ?: "") || tasks.any { it.text.isNotBlank() } || files.isNotEmpty() ||
        participants != (existing?.participantItems ?: emptyList<Item>()) || projects != (existing?.projectItems ?: emptyList<Item>())

    fun close() {
        if (dirty && !busy) confirmClose = true else onClose()
    }
    BackHandler { close() }

    val pickFiles = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        uris.forEach { uri -> files += describe(context, uri) }
    }
    var photo by remember { mutableStateOf<Pair<Uri, String>?>(null) }
    val takePhoto = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { saved ->
        photo?.takeIf { saved }?.let { (uri, name) -> files += PendingFile(uri, name, "image/jpeg", -1) }
    }

    fun save() {
        if (busy) return
        busy = true
        error = null
        scope.launch {
            try {
                val api = app.api!!
                val draft = EntryDraft(
                    type = type, date = date, time = time, title = title.trim(), body = body,
                    agenda = agenda, decisions = decisions, sender = sender, recipients = recipients,
                    tags = tags.map { it.label }, participantItems = participants, projectItems = projects, caseItems = cases,
                    tasks = tasks.filter { it.text.isNotBlank() }.map { NewTask(it.text.trim(), it.due) },
                )
                var saved = savedId?.let { api.updateEntry(it, draft) } ?: api.createEntry(draft)
                savedId = saved.id
                tasks.clear()
                // Nach dem Speichern Anhänge einzeln hochladen; bei einem Fehler
                // bleibt der Eintrag erhalten und nur die fehlenden Dateien stehen noch da.
                while (files.isNotEmpty()) {
                    val file = files.first()
                    saved = api.upload(saved.id, file.name, file.mime, readFile(context, file))
                    files.removeAt(0)
                }
                app.changed()
                onSaved(saved)
            } catch (e: Exception) {
                error = app.handle(e)
            } finally {
                busy = false
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = { close() }) { Icon(Icons.Outlined.Close, "Schließen") } },
                title = { Text(if (existing == null) "Neuer Eintrag" else "Eintrag bearbeiten") },
                actions = {
                    Button(onClick = { save() }, enabled = title.isNotBlank() && !busy, modifier = Modifier.padding(end = 12.dp)) {
                        if (busy) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                        else Text("Speichern")
                    }
                },
            )
        },
    ) { padding ->
        BoxWithConstraints(Modifier.padding(padding).fillMaxSize().imePadding()) {
            val wide = maxWidth >= 720.dp

            val main: @Composable () -> Unit = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    if (error != null) {
                        Surface(color = MaterialTheme.colorScheme.errorContainer, shape = RoundedCornerShape(8.dp)) {
                            Text(error!!, Modifier.padding(12.dp).fillMaxWidth(), color = MaterialTheme.colorScheme.onErrorContainer)
                        }
                    }
                    Text("Typ", style = MaterialTheme.typography.labelLarge)
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        app.types.forEach { (key, label) ->
                            FilterChip(selected = type == key, onClick = { type = key }, label = { Text(label) })
                        }
                    }
                    OutlinedTextField(
                        title, { title = it }, Modifier.fillMaxWidth(), label = { Text("Titel") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                    )
                    if (type == "mail_in" || type == "mail_out") {
                        OutlinedTextField(sender, { sender = it }, Modifier.fillMaxWidth(), label = { Text("Absender") }, singleLine = true)
                        OutlinedTextField(recipients, { recipients = it }, Modifier.fillMaxWidth(), label = { Text("Empfänger") }, singleLine = true)
                    }
                    if (type == "protocol") {
                        OutlinedTextField(agenda, { agenda = it }, Modifier.fillMaxWidth(), label = { Text("Tagesordnung") }, minLines = 3,
                            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences))
                    }
                    OutlinedTextField(
                        body, { body = it }, Modifier.fillMaxWidth(),
                        label = { Text(if (type == "protocol") "Protokolltext" else "Text") },
                        supportingText = { Text("Markdown: **fett**, *kursiv*, - Liste, # Überschrift") },
                        minLines = if (wide) 14 else 8,
                        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                    )
                    if (type == "protocol") {
                        OutlinedTextField(decisions, { decisions = it }, Modifier.fillMaxWidth(), label = { Text("Beschlüsse") }, minLines = 3,
                            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences))
                    }
                }
            }

            val side: @Composable () -> Unit = {
                Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        DateButton(date, { date = it ?: date })
                        TimeButton(time, { time = it })
                    }
                    ItemPicker(app, "Beteiligte", "participants", "new", "Neuer Kontaktvorschlag im Journal", participants, { participants = it })
                    ItemPicker(app, "Projekte", "projects", "new_project", "Neuer Projektvorschlag für ${app.me.value?.schoolYear ?: "dieses Schuljahr"}", projects, { projects = it })
                    ItemPicker(app, "Vorgänge", "cases", "new_case", "Neuer Vorgangsvorschlag im Journal", cases, { cases = it })
                    ItemPicker(app, "Tags", "tags", "tag", "Neuer Tag", tags, { tags = it })
                    HorizontalDivider()
                    Text("Neue Aufgaben", style = MaterialTheme.typography.labelLarge)
                    tasks.forEachIndexed { index, line ->
                        Column {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                OutlinedTextField(line.text, { line.text = it }, Modifier.weight(1f), placeholder = { Text("Aufgabe") }, singleLine = true)
                                IconButton(onClick = { tasks.removeAt(index) }) { Icon(Icons.Outlined.Close, "Aufgabe entfernen") }
                            }
                            DateButton(line.due, { line.due = it }, optional = true, emptyLabel = "Fällig am …")
                        }
                    }
                    OutlinedButton(onClick = { tasks += TaskLine() }) { Icon(Icons.Outlined.Add, null); Text(" Aufgabe hinzufügen") }
                    existing?.tasks?.takeIf { it.isNotEmpty() }?.let {
                        Text("${it.size} vorhandene Aufgaben bleiben unverändert.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    HorizontalDivider()
                    Text("Anhänge", style = MaterialTheme.typography.labelLarge)
                    existing?.attachments?.forEach {
                        Text("${it.name} · ${formatSize(it.size)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    files.forEachIndexed { index, file ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Outlined.AttachFile, null, tint = MaterialTheme.colorScheme.primary)
                            Spacer(Modifier.width(8.dp))
                            Text(file.name + if (file.size >= 0) " · ${formatSize(file.size)}" else "", Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                            IconButton(onClick = { files.removeAt(index) }) { Icon(Icons.Outlined.Close, "Anhang entfernen") }
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilledTonalButton(onClick = { newPhotoUri(context).also { photo = it }.let { takePhoto.launch(it.first) } }) {
                            Icon(Icons.Outlined.PhotoCamera, null); Text(" Foto")
                        }
                        OutlinedButton(onClick = { pickFiles.launch(arrayOf("*/*")) }) { Icon(Icons.Outlined.AttachFile, null); Text(" Datei") }
                    }
                    Text("Höchstens 25 MB je Datei. Anhänge werden nach dem Speichern verschlüsselt im Journal abgelegt.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.size(32.dp))
                }
            }

            if (wide) {
                Row(Modifier.fillMaxSize().padding(horizontal = 24.dp), horizontalArrangement = Arrangement.spacedBy(32.dp)) {
                    Column(Modifier.weight(1.5f).verticalScroll(rememberScrollState()).padding(vertical = 16.dp)) { main() }
                    Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(vertical = 16.dp)) { side() }
                }
            } else {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
                    main()
                    side()
                }
            }
        }
    }

    if (confirmClose) {
        AlertDialog(
            onDismissRequest = { confirmClose = false },
            title = { Text("Änderungen verwerfen?") },
            text = { Text("Der Eintrag ist noch nicht gespeichert.") },
            confirmButton = { TextButton(onClick = { confirmClose = false; onClose() }) { Text("Verwerfen") } },
            dismissButton = { TextButton(onClick = { confirmClose = false }) { Text("Weiter bearbeiten") } },
        )
    }
}
