package de.sljournal.android.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AccountCircle
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.TaskAlt
import androidx.compose.material.icons.outlined.Today
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteScaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import de.sljournal.android.AppViewModel
import de.sljournal.android.ui.editor.EditorRequest
import de.sljournal.android.ui.editor.EntryEditor
import de.sljournal.android.ui.entries.EntriesScreen
import de.sljournal.android.ui.entries.EntryDetail
import de.sljournal.android.ui.login.LoginScreen
import de.sljournal.android.ui.tasks.TasksScreen
import de.sljournal.android.ui.today.TodayScreen

private enum class Destination(val label: String, val icon: ImageVector) {
    TODAY("Heute", Icons.Outlined.Today),
    ENTRIES("Einträge", Icons.Outlined.Description),
    TASKS("Aufgaben", Icons.Outlined.TaskAlt),
    ACCOUNT("Konto", Icons.Outlined.AccountCircle),
}

/** Über der Navigation geöffnete Ansichten: Eintragsdetail und Editor. */
private sealed interface Overlay {
    data class Detail(val id: Int) : Overlay
    data class Editor(val request: EditorRequest) : Overlay
}

@Composable
fun JournalRoot(app: AppViewModel, shared: EditorRequest?, onSharedConsumed: () -> Unit) {
    val session by app.session.collectAsState()
    val notice by app.notice.collectAsState()
    if (session == null) {
        LoginScreen(app, notice)
        return
    }

    var destination by rememberSaveable { mutableStateOf(Destination.TODAY) }
    val overlays = remember { mutableStateListOf<Overlay>() }

    // Inhalte aus „Teilen“ öffnen direkt einen neuen Eintrag.
    LaunchedEffect(shared) {
        if (shared != null) {
            overlays += Overlay.Editor(shared)
            onSharedConsumed()
        }
    }

    fun openEntry(id: Int) { overlays += Overlay.Detail(id) }
    fun newEntry(date: String? = null) { overlays += Overlay.Editor(EditorRequest(date = date)) }
    fun pop() { if (overlays.isNotEmpty()) overlays.removeAt(overlays.lastIndex) }

    NavigationSuiteScaffold(
        navigationSuiteItems = {
            Destination.entries.forEach { target ->
                item(
                    selected = destination == target,
                    onClick = { destination = target },
                    icon = { Icon(target.icon, contentDescription = null) },
                    label = { Text(target.label) },
                )
            }
        },
    ) {
        when (destination) {
            Destination.TODAY -> TodayScreen(app, onOpenEntry = ::openEntry, onNewEntry = { newEntry(it) })
            Destination.ENTRIES -> EntriesScreen(app, onNewEntry = { newEntry() }, onEdit = { overlays += Overlay.Editor(EditorRequest(existing = it)) })
            Destination.TASKS -> TasksScreen(app, onOpenEntry = ::openEntry)
            Destination.ACCOUNT -> AccountScreen(app)
        }
    }

    val top = overlays.lastOrNull() ?: return
    BackHandler { pop() }
    // Außerhalb tippen schließt nur die Detailansicht; der Editor fragt selbst nach.
    OverlayFrame(onDismiss = if (top is Overlay.Detail) ::pop else ({})) {
        when (top) {
            is Overlay.Detail -> EntryDetail(app, top.id, onEdit = { overlays += Overlay.Editor(EditorRequest(existing = it)) }, onBack = ::pop)
            is Overlay.Editor -> EntryEditor(
                app, top.request,
                onClose = ::pop,
                onSaved = { saved ->
                    pop()
                    // Neue Einträge gleich öffnen, bearbeitete aktualisieren sich von selbst.
                    if (top.request.existing == null) overlays += Overlay.Detail(saved.id)
                },
            )
        }
    }
}

/**
 * Telefon: Vollbild. Tablet: großes Blatt über abgedunkeltem Hintergrund,
 * damit die gewohnte Ansicht im Blick bleibt.
 */
@Composable
private fun OverlayFrame(onDismiss: () -> Unit, content: @Composable () -> Unit) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        if (maxWidth < 700.dp) {
            Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) { content() }
        } else {
            Box(
                Modifier.fillMaxSize()
                    .background(Color.Black.copy(alpha = 0.32f))
                    .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null, onClick = onDismiss),
                contentAlignment = Alignment.Center,
            ) {
                Surface(
                    Modifier.safeDrawingPadding().padding(24.dp).widthIn(max = 1100.dp).fillMaxWidth().fillMaxHeight()
                        // Klicks im Blatt nicht an den Hintergrund weiterreichen.
                        .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) {},
                    shape = RoundedCornerShape(24.dp),
                    color = MaterialTheme.colorScheme.background,
                    tonalElevation = 2.dp,
                    shadowElevation = 12.dp,
                ) { content() }
            }
        }
    }
}
