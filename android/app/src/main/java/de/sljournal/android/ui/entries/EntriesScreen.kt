package de.sljournal.android.ui.entries

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Inbox
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.adaptive.ExperimentalMaterial3AdaptiveApi
import androidx.compose.material3.adaptive.layout.AnimatedPane
import androidx.compose.material3.adaptive.layout.ListDetailPaneScaffold
import androidx.compose.material3.adaptive.layout.ListDetailPaneScaffoldRole
import androidx.compose.material3.adaptive.layout.PaneAdaptedValue
import androidx.compose.material3.adaptive.navigation.rememberListDetailPaneScaffoldNavigator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import de.sljournal.android.AppViewModel
import de.sljournal.android.data.Entry
import de.sljournal.android.ui.components.EmptyHint
import de.sljournal.android.ui.components.EntryCard
import de.sljournal.android.ui.components.ErrorState
import de.sljournal.android.ui.voice.CaptureButtons
import kotlinx.coroutines.delay

/**
 * Eintragsliste mit Suche und Typfilter. Auf breiten Bildschirmen stehen Liste
 * und Detail nebeneinander, auf dem Telefon öffnet ein Tipp die Detailansicht.
 */
@OptIn(ExperimentalMaterial3AdaptiveApi::class)
@Composable
fun EntriesScreen(app: AppViewModel, onNewEntry: () -> Unit, onEdit: (Entry) -> Unit, onVoice: () -> Unit) {
    val navigator = rememberListDetailPaneScaffoldNavigator<Int>()
    BackHandler(navigator.canNavigateBack()) { navigator.navigateBack() }
    val selected = navigator.currentDestination?.content
    val detailVisible = navigator.scaffoldValue[ListDetailPaneScaffoldRole.Detail] == PaneAdaptedValue.Expanded
    val listVisible = navigator.scaffoldValue[ListDetailPaneScaffoldRole.List] == PaneAdaptedValue.Expanded

    ListDetailPaneScaffold(
        directive = navigator.scaffoldDirective,
        value = navigator.scaffoldValue,
        listPane = {
            AnimatedPane {
                EntryList(
                    app,
                    selected = if (detailVisible) selected else null,
                    onSelect = { navigator.navigateTo(ListDetailPaneScaffoldRole.Detail, it) },
                    onNewEntry = onNewEntry,
                    onVoice = onVoice,
                )
            }
        },
        detailPane = {
            AnimatedPane {
                if (selected != null) {
                    EntryDetail(app, selected, onEdit = onEdit, onBack = if (listVisible) null else fun() { navigator.navigateBack() })
                } else {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        EmptyHint("Eintrag auswählen", "Links einen Eintrag antippen, um ihn hier zu lesen und zu ergänzen.")
                    }
                }
            }
        },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun EntryList(app: AppViewModel, selected: Int?, onSelect: (Int) -> Unit, onNewEntry: () -> Unit, onVoice: () -> Unit) {
    val revision by app.revision.collectAsState()
    val me by app.me.collectAsState()
    var query by rememberSaveable { mutableStateOf("") }
    var type by rememberSaveable { mutableStateOf<String?>(null) }
    var inbox by rememberSaveable { mutableStateOf(false) }
    val items = remember { mutableStateListOf<Entry>() }
    var page by remember { mutableIntStateOf(1) }
    var pages by remember { mutableIntStateOf(1) }
    var total by remember { mutableIntStateOf(0) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var retry by remember { mutableIntStateOf(0) }
    val listState = rememberLazyListState()

    // Neue Suche: kurz warten, dann ab Seite 1 laden.
    LaunchedEffect(query, type, inbox, revision, retry) {
        delay(if (query.isBlank()) 0 else 350)
        loading = true
        error = null
        try {
            val result = app.api!!.entries(query.ifBlank { null }, type, 1, inbox)
            items.clear(); items.addAll(result.items)
            page = 1; pages = result.pages; total = result.total
        } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e
            error = app.handle(e)
        } finally {
            loading = false
        }
    }
    val nearEnd by remember { derivedStateOf { (listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0) >= items.size - 5 } }
    LaunchedEffect(nearEnd, page, pages) {
        if (nearEnd && !loading && page < pages && error == null) {
            loading = true
            try {
                val result = app.api!!.entries(query.ifBlank { null }, type, page + 1, inbox)
                items.addAll(result.items.filter { new -> items.none { it.id == new.id } })
                page = result.page; pages = result.pages
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                error = app.handle(e)
            } finally {
                loading = false
            }
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Einträge") }) },
        floatingActionButton = { CaptureButtons(onVoice = onVoice, onNewEntry = onNewEntry) },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            OutlinedTextField(
                query, { query = it },
                Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                placeholder = { Text("Titel, Text, Beteiligte, Tags …") },
                leadingIcon = { Icon(Icons.Outlined.Search, null) },
                trailingIcon = { if (query.isNotEmpty()) IconButton(onClick = { query = "" }) { Icon(Icons.Outlined.Close, "Suche leeren") } },
                singleLine = true,
            )
            LazyRow(contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                item {
                    FilterChip(
                        selected = inbox, onClick = { inbox = !inbox },
                        label = { Text("Posteingang" + (me?.inboxCount?.takeIf { it > 0 }?.let { " ($it)" } ?: "")) },
                        leadingIcon = { Icon(Icons.Outlined.Inbox, null) },
                    )
                }
                item { FilterChip(selected = type == null, onClick = { type = null }, label = { Text("Alle Typen") }) }
                items(app.types.entries.toList()) { (key, label) ->
                    FilterChip(selected = type == key, onClick = { type = if (type == key) null else key }, label = { Text(label) })
                }
            }
            Row(Modifier.padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(if (loading && items.isEmpty()) "Wird geladen …" else "$total Einträge", style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            when {
                error != null && items.isEmpty() -> ErrorState(error!!) { retry++ }
                !loading && items.isEmpty() -> EmptyHint(if (query.isBlank()) "Noch keine Einträge" else "Keine Treffer für „$query“")
                else -> LazyColumn(
                    state = listState,
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 96.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(items, key = { it.id }) { entry ->
                        EntryCard(entry, selected = entry.id == selected, showDate = true) { onSelect(entry.id) }
                    }
                    if (loading) item { Box(Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() } }
                }
            }
        }
    }
}
