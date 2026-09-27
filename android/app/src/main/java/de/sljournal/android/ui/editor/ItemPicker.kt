package de.sljournal.android.ui.editor

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.InputChip
import androidx.compose.material3.InputChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import de.sljournal.android.AppViewModel
import de.sljournal.android.data.Item
import kotlinx.coroutines.delay

/**
 * Auswahlfeld mit Autovervollständigung wie in der Weboberfläche: vorhandene
 * Kontakte, Projekte, Vorgänge oder Tags wählen, oder einen neuen Namen
 * eintragen, der im Journal als Vorschlag erscheint.
 *
 * @param kind Name der Vorschlagsliste auf dem Server (participants, projects, cases, tags)
 * @param newKind Art eines frei eingegebenen Werts (new, new_project, new_case, tag)
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ItemPicker(
    app: AppViewModel,
    label: String,
    kind: String,
    newKind: String,
    newHint: String,
    selected: List<Item>,
    onChange: (List<Item>) -> Unit,
    modifier: Modifier = Modifier,
) {
    var text by remember { mutableStateOf("") }
    var focused by remember { mutableStateOf(false) }
    var suggestions by remember { mutableStateOf<List<Item>>(emptyList()) }

    LaunchedEffect(text, focused) {
        if (!focused) return@LaunchedEffect
        delay(200)
        suggestions = runCatching { app.api!!.autocomplete(kind, text.trim()) }.getOrElse { app.handle(it); emptyList() }
    }

    fun same(a: Item, b: Item) = if (a.id != null && b.id != null) a.kind == b.kind && a.id == b.id else a.label.equals(b.label, ignoreCase = true)

    fun add(item: Item) {
        if (selected.none { same(it, item) }) onChange(selected + item)
        text = ""
    }

    fun addTyped() {
        val value = text.trim().trimStart('#')
        if (value.isEmpty()) return
        val match = suggestions.firstOrNull { it.label.equals(value, ignoreCase = true) }
        add(match ?: Item(kind = newKind, label = value, schoolYear = app.me.value?.schoolYear?.takeIf { newKind == "new_project" }))
    }

    Column(modifier) {
        Text(label, style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(bottom = 4.dp))
        if (selected.isNotEmpty()) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                selected.forEach { item ->
                    val isNew = item.id == null && item.kind != "tag"
                    InputChip(
                        selected = false,
                        onClick = { onChange(selected - item) },
                        label = { Text(item.label + if (isNew) " · neu" else "") },
                        trailingIcon = { Icon(Icons.Outlined.Close, "Entfernen", Modifier.size(InputChipDefaults.IconSize)) },
                    )
                }
            }
        }
        OutlinedTextField(
            text, { text = it },
            Modifier.fillMaxWidth().onFocusChanged { focused = it.isFocused },
            placeholder = { Text("Suchen oder neu eingeben …") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { addTyped() }),
        )
        val visible = suggestions.filter { s -> selected.none { same(it, s) } }.take(6)
        val typed = text.trim().trimStart('#')
        val offerNew = typed.isNotEmpty() && visible.none { it.label.equals(typed, ignoreCase = true) }
        if (focused && (visible.isNotEmpty() || offerNew)) {
            OutlinedCard(Modifier.fillMaxWidth().padding(top = 4.dp)) {
                visible.forEach { item ->
                    Column(Modifier.fillMaxWidth().clickable { add(item) }.padding(horizontal = 14.dp, vertical = 10.dp)) {
                        Text(item.label, style = MaterialTheme.typography.bodyMedium)
                        item.detail?.takeIf { it.isNotBlank() }?.let {
                            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                if (offerNew) {
                    Row(Modifier.fillMaxWidth().clickable { addTyped() }.padding(horizontal = 14.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.Add, null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.width(8.dp))
                        Column {
                            Text("„$typed“ übernehmen", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary)
                            Text(newHint, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}
