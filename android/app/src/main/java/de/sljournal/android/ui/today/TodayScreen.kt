package de.sljournal.android.ui.today

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.Event
import androidx.compose.material.icons.outlined.NotificationsActive
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import de.sljournal.android.AppViewModel
import de.sljournal.android.data.Day
import de.sljournal.android.data.EntryDraft
import de.sljournal.android.ui.components.EmptyHint
import de.sljournal.android.ui.components.EntryCard
import de.sljournal.android.ui.components.ErrorState
import de.sljournal.android.ui.components.Load
import de.sljournal.android.ui.components.Loading
import de.sljournal.android.ui.components.SectionTitle
import de.sljournal.android.ui.components.TaskRow
import de.sljournal.android.ui.components.dayOfMonth
import de.sljournal.android.ui.components.longDate
import de.sljournal.android.ui.components.rememberLoader
import de.sljournal.android.ui.components.shortDate
import de.sljournal.android.ui.components.weekdayShort
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/**
 * Tagescockpit. Telefon: eine Spalte. Tablet: links Termine, Journal und
 * Einträge des Tages, rechts Aufgaben und Wiedervorlagen – wie im Browser.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TodayScreen(app: AppViewModel, onOpenEntry: (Int) -> Unit, onNewEntry: (date: String) -> Unit) {
    val me by app.me.collectAsState()
    var date by rememberSaveable { mutableStateOf<String?>(null) }
    val loader = rememberLoader(app, date) { it.day(date) }
    val today = me?.today ?: LocalDate.now().toString()
    val shown = (loader.state as? Load.Ok)?.value?.date ?: date ?: today
    var picking by remember { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        DateTile(shown)
                        Spacer(Modifier.width(12.dp))
                        Column {
                            Text(if (shown == today) "Heute" else longDate(shown).substringBefore(","), style = MaterialTheme.typography.titleMedium)
                            Text(longDate(shown).substringAfter(", "), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                },
                actions = {
                    val day = loader.value
                    IconButton(onClick = { date = day?.previous ?: LocalDate.parse(shown).minusDays(1).toString() }) {
                        Icon(Icons.AutoMirrored.Outlined.KeyboardArrowLeft, "Vorheriger Tag")
                    }
                    IconButton(onClick = { picking = true }) { Icon(Icons.Outlined.CalendarMonth, "Datum wählen") }
                    IconButton(onClick = { date = day?.following ?: LocalDate.parse(shown).plusDays(1).toString() }) {
                        Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, "Nächster Tag")
                    }
                    if (shown != today) TextButton(onClick = { date = null }) { Text("Heute") }
                    IconButton(onClick = loader.reload) { Icon(Icons.Outlined.Refresh, "Aktualisieren") }
                },
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { onNewEntry(shown) },
                icon = { Icon(Icons.Outlined.Add, null) },
                text = { Text("Neuer Eintrag") },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            when (val state = loader.state) {
                Load.Loading -> Loading()
                is Load.Failed -> ErrorState(state.message, loader.reload)
                is Load.Ok -> {
                    val day = state.value
                    val toggle: (Int) -> Unit = { id ->
                        scope.launch {
                            runCatching { app.api!!.toggleTask(id) }
                                .onSuccess { app.changed() }
                                .onFailure { snackbar.showSnackbar(app.handle(it)) }
                        }
                    }
                    val quickNote: @Composable () -> Unit = {
                        QuickJournal(day.date, today, onSave = { text ->
                            val lines = text.trim().lines()
                            val draft = EntryDraft(
                                type = "journal",
                                date = day.date,
                                time = if (day.date == today) LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm")) else "",
                                title = lines.first().take(120),
                                body = lines.drop(1).joinToString("\n").trim(),
                            )
                            runCatching { app.api!!.createEntry(draft) }
                                .onSuccess { app.changed(); snackbar.showSnackbar("Im Tagesjournal gespeichert.") }
                                .onFailure { snackbar.showSnackbar(app.handle(it)) }
                                .isSuccess
                        })
                    }
                    BoxWithConstraints(Modifier.fillMaxSize()) {
                        if (maxWidth >= 720.dp) {
                            Row(Modifier.fillMaxSize().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                                LazyColumn(Modifier.weight(1.6f), contentPadding = PaddingValues(vertical = 16.dp, horizontal = 8.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                    item { quickNote() }
                                    events(day)
                                    dayEntries(day, onOpenEntry)
                                    item { Spacer(Modifier.size(80.dp)) }
                                }
                                LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(vertical = 16.dp, horizontal = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    reminders(day)
                                    tasks(day, today, toggle, onOpenEntry)
                                    item { Spacer(Modifier.size(80.dp)) }
                                }
                            }
                        } else {
                            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                item { quickNote() }
                                reminders(day)
                                events(day)
                                dayEntries(day, onOpenEntry)
                                tasks(day, today, toggle, onOpenEntry)
                                item { Spacer(Modifier.size(80.dp)) }
                            }
                        }
                    }
                }
            }
        }
    }

    if (picking) {
        val initial = LocalDate.parse(shown).atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli()
        val pickerState = rememberDatePickerState(initialSelectedDateMillis = initial)
        DatePickerDialog(
            onDismissRequest = { picking = false },
            confirmButton = {
                TextButton(onClick = {
                    pickerState.selectedDateMillis?.let { date = Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate().toString() }
                    picking = false
                }) { Text("Übernehmen") }
            },
            dismissButton = { TextButton(onClick = { picking = false }) { Text("Abbrechen") } },
        ) { DatePicker(pickerState) }
    }
}

@Composable
private fun DateTile(date: String) {
    Surface(shape = RoundedCornerShape(9.dp), color = MaterialTheme.colorScheme.surface, tonalElevation = 1.dp, border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.padding(horizontal = 10.dp, vertical = 2.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(dayOfMonth(date), style = MaterialTheme.typography.titleMedium)
            Text(weekdayShort(date), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun QuickJournal(date: String, today: String, onSave: suspend (String) -> Boolean) {
    var text by rememberSaveable(date) { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    OutlinedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text("Journal", style = MaterialTheme.typography.titleMedium)
            Text(
                if (date == today) "Kurz festhalten, was heute war. Die erste Zeile wird zum Titel."
                else "Nachtrag für den ${shortDate(date)}. Die erste Zeile wird zum Titel.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(text, { text = it }, Modifier.fillMaxWidth().padding(top = 8.dp), minLines = 3, placeholder = { Text("Notiz für das Tagesjournal …") })
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.End) {
                Button(enabled = text.isNotBlank() && !busy, onClick = {
                    busy = true
                    scope.launch {
                        if (onSave(text)) text = ""
                        busy = false
                    }
                }) { Text("Im Journal speichern") }
            }
        }
    }
}

private fun LazyListScope.events(day: Day) {
    if (day.events.isEmpty()) return
    item { SectionTitle("Termine", day.events.size) }
    items(day.events) { event ->
        Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.Top) {
            Column(Modifier.width(64.dp)) {
                Text(if (event.allDay) "Ganztägig" else event.time, style = MaterialTheme.typography.labelLarge)
                if (event.end.isNotEmpty()) Text(event.end, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Surface(Modifier.size(3.dp, 36.dp), color = MaterialTheme.colorScheme.primary) {}
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(event.title, style = MaterialTheme.typography.bodyLarge)
                Text(listOf(event.calendar, event.location).filter { it.isNotBlank() }.joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

private fun LazyListScope.dayEntries(day: Day, onOpenEntry: (Int) -> Unit) {
    item { SectionTitle("Einträge des Tages", day.entries.size) }
    if (day.entries.isEmpty()) {
        item { EmptyHint("Noch keine Einträge an diesem Tag", icon = Icons.Outlined.Event) }
    }
    items(day.entries, key = { "entry-${it.id}" }) { entry -> EntryCard(entry) { onOpenEntry(entry.id) } }
}

private fun LazyListScope.reminders(day: Day) {
    if (day.caseReminders.isEmpty()) return
    item {
        Surface(color = MaterialTheme.colorScheme.tertiaryContainer, shape = RoundedCornerShape(10.dp), modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.NotificationsActive, null, tint = MaterialTheme.colorScheme.onTertiaryContainer)
                    Spacer(Modifier.width(8.dp))
                    Text("Wiedervorlagen", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onTertiaryContainer)
                }
                day.caseReminders.forEach {
                    Text("${it.title} · ${shortDate(it.followUp)}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onTertiaryContainer, modifier = Modifier.padding(top = 4.dp))
                }
            }
        }
    }
}

private fun LazyListScope.tasks(day: Day, today: String, toggle: (Int) -> Unit, onOpenEntry: (Int) -> Unit) {
    item { SectionTitle("Aufgaben", day.taskGroups.sumOf { it.tasks.size }) }
    day.taskGroups.forEach { group ->
        item(key = "group-${group.key}") {
            Text(group.label, style = MaterialTheme.typography.labelLarge,
                color = if (group.key == "overdue" && group.tasks.isNotEmpty()) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 8.dp))
        }
        if (group.tasks.isEmpty()) {
            item { Text("Keine", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = 12.dp, top = 2.dp)) }
        }
        items(group.tasks, key = { "task-${group.key}-${it.id}" }) { TaskRow(it, today, { toggle(it.id) }, onOpenEntry) }
    }
    if (day.undatedCount > 0) {
        item { Text("${day.undatedCount} offene Aufgaben ohne Datum", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp)) }
    }
    if (day.completedTasks.isNotEmpty()) {
        item { Text("An diesem Tag erledigt", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 12.dp)) }
        items(day.completedTasks, key = { "done-${it.id}" }) { TaskRow(it, today, { toggle(it.id) }, onOpenEntry) }
    }
}
