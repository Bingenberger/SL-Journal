package de.sljournal.android.ui.entries

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.AttachFile
import androidx.compose.material.icons.outlined.Draw
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.PhotoCamera
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import de.sljournal.android.AppViewModel
import de.sljournal.android.data.Entry
import de.sljournal.android.data.TaskDraft
import de.sljournal.android.ui.components.EntryChips
import de.sljournal.android.ui.components.ErrorState
import de.sljournal.android.ui.components.Load
import de.sljournal.android.ui.components.Loading
import de.sljournal.android.ui.components.MarkdownText
import de.sljournal.android.ui.components.SectionTitle
import de.sljournal.android.ui.components.TaskDialog
import de.sljournal.android.ui.components.TaskRow
import de.sljournal.android.ui.components.describe
import de.sljournal.android.ui.components.formatSize
import de.sljournal.android.ui.components.longDate
import de.sljournal.android.ui.components.newPhotoUri
import de.sljournal.android.ui.components.openAttachment
import de.sljournal.android.ui.components.readFile
import de.sljournal.android.ui.components.rememberLoader
import de.sljournal.android.ui.components.typeColor
import de.sljournal.android.ui.components.typeIcon
import kotlinx.coroutines.launch
import java.time.LocalDate

/**
 * Detailansicht eines Eintrags. Als Detailbereich neben der Liste (Tablet) oder
 * als eigener Bildschirm (Telefon). [onBack] blendet den Zurück-Pfeil ein.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EntryDetail(app: AppViewModel, entryId: Int, onEdit: (Entry) -> Unit, onBack: (() -> Unit)?) {
    val loader = rememberLoader(app, entryId) { it.entry(entryId) }
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var busy by remember { mutableStateOf(false) }
    var addingTask by remember { mutableStateOf(false) }
    val today = app.me.value?.today ?: LocalDate.now().toString()

    fun upload(uris: List<Uri>, names: Map<Uri, String> = emptyMap()) {
        if (uris.isEmpty()) return
        busy = true
        scope.launch {
            try {
                var latest: Entry? = null
                for (uri in uris) {
                    val file = describe(context, uri).let { f -> names[uri]?.let { f.copy(name = it, mime = "image/jpeg") } ?: f }
                    latest = app.api!!.upload(entryId, file.name, file.mime, readFile(context, file))
                }
                latest?.let { loader.set(it) }
                app.changed()
                snackbar.showSnackbar(if (uris.size == 1) "Anhang gespeichert." else "${uris.size} Anhänge gespeichert.")
            } catch (e: Exception) {
                snackbar.showSnackbar(app.handle(e))
            } finally {
                busy = false
            }
        }
    }

    val pickFiles = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { upload(it) }
    var photo by remember { mutableStateOf<Pair<Uri, String>?>(null) }
    val takePhoto = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { saved ->
        val target = photo
        if (saved && target != null) upload(listOf(target.first), mapOf(target.first to target.second))
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(loader.value?.typeLabel ?: "Eintrag") },
                navigationIcon = { if (onBack != null) IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Zurück") } },
                actions = {
                    IconButton(onClick = loader.reload) { Icon(Icons.Outlined.Refresh, "Aktualisieren") }
                    loader.value?.let { entry -> IconButton(onClick = { onEdit(entry) }) { Icon(Icons.Outlined.Edit, "Eintrag bearbeiten") } }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            when (val state = loader.state) {
                Load.Loading -> Loading()
                is Load.Failed -> ErrorState(state.message, loader.reload)
                is Load.Ok -> {
                    val entry = state.value
                    Column(Modifier.fillMaxSize()) {
                        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                        BoxWithConstraints(Modifier.fillMaxSize()) {
                            val twoColumns = maxWidth >= 760.dp
                            Row(
                                Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 12.dp),
                                horizontalArrangement = Arrangement.spacedBy(24.dp),
                            ) {
                                Column(Modifier.weight(1.6f), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                                    Header(entry)
                                    Content(entry)
                                    if (!twoColumns) Side(entry, today, busy, onToggle = { toggle(app, it, loader.reload, snackbar, scope) }, onAddTask = { addingTask = true },
                                        onPickFiles = { pickFiles.launch(arrayOf("*/*")) },
                                        onPhoto = { newPhotoUri(context).also { photo = it }.let { takePhoto.launch(it.first) } },
                                        onOpen = { id, name, mime -> open(app, context, id, name, mime, snackbar, scope) })
                                    Spacer(Modifier.size(24.dp))
                                }
                                if (twoColumns) {
                                    Column(Modifier.weight(1f).widthIn(max = 420.dp)) {
                                        Side(entry, today, busy, onToggle = { toggle(app, it, loader.reload, snackbar, scope) }, onAddTask = { addingTask = true },
                                            onPickFiles = { pickFiles.launch(arrayOf("*/*")) },
                                            onPhoto = { newPhotoUri(context).also { photo = it }.let { takePhoto.launch(it.first) } },
                                            onOpen = { id, name, mime -> open(app, context, id, name, mime, snackbar, scope) })
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (addingTask) {
        TaskDialog(onDismiss = { addingTask = false }) { text, due ->
            runCatching { app.api!!.createTask(TaskDraft(text, due, entryId)) }
                .onSuccess { loader.reload(); app.changed() }
                .exceptionOrNull()?.let { app.handle(it) }
        }
    }
}

private fun toggle(app: AppViewModel, id: Int, reload: () -> Unit, snackbar: SnackbarHostState, scope: kotlinx.coroutines.CoroutineScope) {
    scope.launch {
        runCatching { app.api!!.toggleTask(id) }
            .onSuccess { reload(); app.changed() }
            .onFailure { snackbar.showSnackbar(app.handle(it)) }
    }
}

private fun open(app: AppViewModel, context: android.content.Context, id: Int, name: String, mime: String, snackbar: SnackbarHostState, scope: kotlinx.coroutines.CoroutineScope) {
    scope.launch {
        try {
            openAttachment(context, name, mime, app.api!!.download(id))?.let { snackbar.showSnackbar(it) }
        } catch (e: Exception) {
            snackbar.showSnackbar(app.handle(e))
        }
    }
}

@Composable
private fun Header(entry: Entry) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(typeIcon(entry.type), null, Modifier.size(18.dp), tint = typeColor(entry.type))
            Spacer(Modifier.width(6.dp))
            Text(entry.typeLabel.uppercase(), style = MaterialTheme.typography.labelMedium, color = typeColor(entry.type))
        }
        Text(entry.title, style = MaterialTheme.typography.headlineSmall)
        Text(longDate(entry.date) + if (entry.time.isNotEmpty()) " · ${entry.time} Uhr" else "",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (entry.needsReview) {
            Surface(color = MaterialTheme.colorScheme.tertiaryContainer, shape = RoundedCornerShape(8.dp)) {
                Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.Warning, null, tint = MaterialTheme.colorScheme.onTertiaryContainer)
                    Spacer(Modifier.width(8.dp))
                    Text("Die Mailangaben wurden nicht vollständig erkannt. Bitte Datum, Absender und Empfänger prüfen.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onTertiaryContainer)
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Content(entry: Entry) {
    val meta = buildList {
        if (entry.sender.isNotBlank()) add("Von" to entry.sender)
        if (entry.recipients.isNotBlank()) add("An" to entry.recipients)
    }
    meta.forEach { (label, value) ->
        Row {
            Text(label, Modifier.width(96.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
            Text(value, style = MaterialTheme.typography.bodyMedium)
        }
    }
    if (entry.participantItems.isNotEmpty()) {
        Row {
            Text("Beteiligte", Modifier.width(96.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                entry.participantItems.forEach { de.sljournal.android.ui.components.Pill(it.label, warning = it.kind != "person") }
            }
        }
    }
    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        entry.projectItems.filter { it.kind == "new_project" }.forEach { de.sljournal.android.ui.components.Pill(it.label + " · Vorschlag", warning = true) }
        entry.caseItems.filter { it.kind == "new_case" }.forEach { de.sljournal.android.ui.components.Pill(it.label + " · Vorschlag", warning = true) }
    }
    EntryChips(entry.copy(attachmentCount = 0, drawingCount = 0))
    HorizontalDivider()
    if (entry.type == "protocol" && entry.agenda.isNotBlank()) {
        Text("Tagesordnung", style = MaterialTheme.typography.titleMedium)
        MarkdownText(entry.agenda)
        Text("Protokolltext", style = MaterialTheme.typography.titleMedium)
    }
    if (entry.body.isNotBlank()) MarkdownText(entry.body)
    else if (entry.type != "protocol") Text("Kein Text", color = MaterialTheme.colorScheme.onSurfaceVariant)
    if (entry.type == "protocol" && entry.decisions.isNotBlank()) {
        Text("Beschlüsse", style = MaterialTheme.typography.titleMedium)
        MarkdownText(entry.decisions)
    }
    if (entry.drawings.isNotEmpty()) {
        OutlinedCard(Modifier.fillMaxWidth()) {
            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Draw, null, tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(12.dp))
                Text("${entry.drawings.size} Zeichenblätter. Handschrift und Skizzen öffnen Sie in der Weboberfläche.",
                    style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun Side(
    entry: Entry,
    today: String,
    busy: Boolean,
    onToggle: (Int) -> Unit,
    onAddTask: () -> Unit,
    onPickFiles: () -> Unit,
    onPhoto: () -> Unit,
    onOpen: (Int, String, String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        SectionTitle("Aufgaben", entry.tasks.size) {
            TextButton(onClick = onAddTask) { Icon(Icons.Outlined.Add, null); Text(" Neu") }
        }
        if (entry.tasks.isEmpty()) Text("Noch keine Aufgaben", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        entry.tasks.forEach { TaskRow(it, today, { onToggle(it.id) }) }
        Spacer(Modifier.size(12.dp))
        SectionTitle("Anhänge", entry.attachments.size)
        entry.attachments.forEach { a ->
            Row(
                Modifier.fillMaxWidth().clickable { onOpen(a.id, a.name, a.mime) }.padding(vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Outlined.AttachFile, null, tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(a.name, style = MaterialTheme.typography.bodyMedium)
                    Text(formatSize(a.size), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 4.dp)) {
            FilledTonalButton(onClick = onPhoto, enabled = !busy) { Icon(Icons.Outlined.PhotoCamera, null); Text(" Foto") }
            OutlinedButton(onClick = onPickFiles, enabled = !busy) { Icon(Icons.Outlined.AttachFile, null); Text(" Datei") }
        }
    }
}
