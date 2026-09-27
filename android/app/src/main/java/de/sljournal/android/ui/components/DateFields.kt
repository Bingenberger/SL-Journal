package de.sljournal.android.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TimePicker
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberTimePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

/** Knopf mit Datum, öffnet den Kalender. [optional] erlaubt „Ohne Datum“. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DateButton(value: String?, onChange: (String?) -> Unit, modifier: Modifier = Modifier, optional: Boolean = false, emptyLabel: String = "Ohne Datum") {
    var open by remember { mutableStateOf(false) }
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        OutlinedButton(onClick = { open = true }) {
            Icon(Icons.Outlined.CalendarMonth, null)
            Text("  " + (value?.let { shortDate(it) } ?: emptyLabel))
        }
        if (optional && value != null) {
            IconButton(onClick = { onChange(null) }) { Icon(Icons.Outlined.Close, "Datum entfernen") }
        }
    }
    if (open) {
        val initial = (parseDate(value) ?: LocalDate.now()).atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli()
        val state = rememberDatePickerState(initialSelectedDateMillis = initial)
        DatePickerDialog(
            onDismissRequest = { open = false },
            confirmButton = {
                TextButton(onClick = {
                    state.selectedDateMillis?.let { onChange(Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate().toString()) }
                    open = false
                }) { Text("Übernehmen") }
            },
            dismissButton = { TextButton(onClick = { open = false }) { Text("Abbrechen") } },
        ) { DatePicker(state) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TimeButton(value: String, onChange: (String) -> Unit, modifier: Modifier = Modifier) {
    var open by remember { mutableStateOf(false) }
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        OutlinedButton(onClick = { open = true }) {
            Icon(Icons.Outlined.Schedule, null)
            Text("  " + value.ifEmpty { "Ohne Uhrzeit" })
        }
        if (value.isNotEmpty()) IconButton(onClick = { onChange("") }) { Icon(Icons.Outlined.Close, "Uhrzeit entfernen") }
    }
    if (open) {
        val parts = value.split(":").mapNotNull { it.toIntOrNull() }
        val now = java.time.LocalTime.now()
        val state = rememberTimePickerState(parts.getOrElse(0) { now.hour }, parts.getOrElse(1) { now.minute }, is24Hour = true)
        AlertDialog(
            onDismissRequest = { open = false },
            confirmButton = {
                TextButton(onClick = {
                    onChange("%02d:%02d".format(state.hour, state.minute))
                    open = false
                }) { Text("Übernehmen") }
            },
            dismissButton = { TextButton(onClick = { open = false }) { Text("Abbrechen") } },
            text = { TimePicker(state) },
        )
    }
}

/** Neue Aufgabe: Text und optionales Fälligkeitsdatum. */
@Composable
fun TaskDialog(title: String = "Neue Aufgabe", onDismiss: () -> Unit, onSave: suspend (text: String, due: String?) -> String?) {
    var text by remember { mutableStateOf("") }
    var due by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(text, { text = it }, Modifier.fillMaxWidth(), label = { Text("Aufgabe") }, minLines = 2)
                DateButton(due, { due = it }, optional = true, emptyLabel = "Fällig am …")
                if (error != null) Text(error!!, color = androidx.compose.material3.MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 4.dp))
            }
        },
        confirmButton = {
            TextButton(enabled = text.isNotBlank() && !busy, onClick = {
                busy = true
                scope.launch {
                    error = onSave(text.trim(), due)
                    busy = false
                    if (error == null) onDismiss()
                }
            }) { Text("Speichern") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}
