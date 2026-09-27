package de.sljournal.android.ui.tasks

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import de.sljournal.android.AppViewModel
import de.sljournal.android.data.Task
import de.sljournal.android.data.TaskDraft
import de.sljournal.android.ui.components.EmptyHint
import de.sljournal.android.ui.components.ErrorState
import de.sljournal.android.ui.components.Load
import de.sljournal.android.ui.components.Loading
import de.sljournal.android.ui.components.TaskDialog
import de.sljournal.android.ui.components.TaskRow
import de.sljournal.android.ui.components.rememberLoader
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.LocalDate

private val FILTERS = listOf("open" to "Offen", "undated" to "Ohne Datum", "done" to "Erledigt")

/**
 * Aufgaben nach Fälligkeit gruppiert. Das Raster nutzt auf dem Tablet mehrere
 * Spalten, sodass Überfällig, Diese Woche und Später nebeneinander stehen.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TasksScreen(app: AppViewModel, onOpenEntry: (Int) -> Unit) {
    val me by app.me.collectAsState()
    var filter by rememberSaveable { mutableStateOf("open") }
    var input by rememberSaveable { mutableStateOf("") }
    var query by rememberSaveable { mutableStateOf("") }
    LaunchedEffect(input) { delay(300); query = input }
    val loader = rememberLoader(app, filter, query) { it.tasks(filter, query.ifBlank { null }) }
    var adding by remember { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val today = me?.today ?: LocalDate.now().toString()

    Scaffold(
        topBar = { TopAppBar(title = { Text("Aufgaben") }) },
        floatingActionButton = {
            ExtendedFloatingActionButton(onClick = { adding = true }, icon = { Icon(Icons.Outlined.Add, null) }, text = { Text("Neue Aufgabe") })
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                FILTERS.forEachIndexed { index, (key, label) ->
                    SegmentedButton(
                        selected = filter == key,
                        onClick = { filter = key },
                        shape = SegmentedButtonDefaults.itemShape(index, FILTERS.size),
                    ) { Text(label) }
                }
            }
            OutlinedTextField(
                input, { input = it },
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                placeholder = { Text("Aufgaben durchsuchen") },
                leadingIcon = { Icon(Icons.Outlined.Search, null) },
                trailingIcon = { if (input.isNotEmpty()) IconButton(onClick = { input = "" }) { Icon(Icons.Outlined.Close, "Suche leeren") } },
                singleLine = true,
            )
            Box(Modifier.fillMaxSize()) {
                when (val state = loader.state) {
                    Load.Loading -> Loading()
                    is Load.Failed -> ErrorState(state.message, loader.reload)
                    is Load.Ok -> {
                        val groups = group(state.value, filter, today)
                        if (groups.isEmpty()) {
                            EmptyHint(if (query.isBlank()) "Keine Aufgaben in dieser Ansicht" else "Keine Treffer")
                        } else {
                            LazyVerticalGrid(
                                columns = GridCells.Adaptive(minSize = 340.dp),
                                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 96.dp),
                                horizontalArrangement = Arrangement.spacedBy(16.dp),
                                verticalArrangement = Arrangement.spacedBy(16.dp),
                            ) {
                                items(groups, key = { it.first }) { (label, tasks) ->
                                    OutlinedCard(Modifier.fillMaxWidth()) {
                                        Column(Modifier.padding(start = 4.dp, end = 12.dp, top = 12.dp, bottom = 8.dp)) {
                                            Text(
                                                "$label · ${tasks.size}",
                                                style = MaterialTheme.typography.titleSmall,
                                                color = if (label == "Überfällig") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
                                                modifier = Modifier.padding(start = 12.dp, bottom = 4.dp),
                                            )
                                            tasks.forEach { task ->
                                                TaskRow(task, today, onToggle = {
                                                    scope.launch {
                                                        runCatching { app.api!!.toggleTask(task.id) }
                                                            .onSuccess { app.changed() }
                                                            .onFailure { snackbar.showSnackbar(app.handle(it)) }
                                                    }
                                                }, onOpenEntry = onOpenEntry)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (adding) {
        TaskDialog(onDismiss = { adding = false }) { text, due ->
            runCatching { app.api!!.createTask(TaskDraft(text, due)) }
                .onSuccess { app.changed() }
                .exceptionOrNull()?.let { app.handle(it) }
        }
    }
}

private fun group(tasks: List<Task>, filter: String, today: String): List<Pair<String, List<Task>>> {
    if (filter != "open") return if (tasks.isEmpty()) emptyList() else listOf((if (filter == "done") "Erledigt" else "Ohne Datum") to tasks)
    val week = LocalDate.parse(today).plusDays(7).toString()
    val buckets = linkedMapOf<String, MutableList<Task>>(
        "Überfällig" to mutableListOf(), "Heute" to mutableListOf(), "Nächste 7 Tage" to mutableListOf(),
        "Später" to mutableListOf(), "Ohne Datum" to mutableListOf(),
    )
    tasks.forEach { t ->
        val key = when {
            t.due == null -> "Ohne Datum"
            t.due < today -> "Überfällig"
            t.due == today -> "Heute"
            t.due <= week -> "Nächste 7 Tage"
            else -> "Später"
        }
        buckets.getValue(key).add(t)
    }
    return buckets.filterValues { it.isNotEmpty() }.map { it.key to it.value.toList() }
}
