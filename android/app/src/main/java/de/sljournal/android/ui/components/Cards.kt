package de.sljournal.android.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.CallMade
import androidx.compose.material.icons.automirrored.outlined.CallReceived
import androidx.compose.material.icons.outlined.AttachFile
import androidx.compose.material.icons.outlined.Call
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.Draw
import androidx.compose.material.icons.outlined.EditNote
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material.icons.outlined.Forum
import androidx.compose.material.icons.outlined.Gavel
import androidx.compose.material.icons.automirrored.outlined.Label
import androidx.compose.material.icons.outlined.RadioButtonUnchecked
import androidx.compose.material.icons.automirrored.outlined.StickyNote2
import androidx.compose.material.icons.outlined.Work
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import de.sljournal.android.data.Entry
import de.sljournal.android.data.Task

fun typeIcon(type: String): ImageVector = when (type) {
    "mail_in" -> Icons.AutoMirrored.Outlined.CallReceived
    "mail_out" -> Icons.AutoMirrored.Outlined.CallMade
    "meeting" -> Icons.Outlined.Forum
    "protocol" -> Icons.Outlined.Gavel
    "phone" -> Icons.Outlined.Call
    "journal" -> Icons.Outlined.EditNote
    else -> Icons.AutoMirrored.Outlined.StickyNote2
}

@Composable
fun typeColor(type: String): Color = when (type) {
    "mail_in" -> Color(0xFF6388A5)
    "mail_out" -> Color(0xFF9A84AE)
    "phone" -> Color(0xFFB4946C)
    else -> MaterialTheme.colorScheme.primary
}

@Composable
fun Pill(text: String, icon: ImageVector? = null, warning: Boolean = false) {
    Surface(
        shape = RoundedCornerShape(6.dp),
        color = if (warning) MaterialTheme.colorScheme.tertiaryContainer else MaterialTheme.colorScheme.secondaryContainer,
        contentColor = if (warning) MaterialTheme.colorScheme.onTertiaryContainer else MaterialTheme.colorScheme.onSecondaryContainer,
    ) {
        Row(Modifier.padding(horizontal = 8.dp, vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
            if (icon != null) {
                Icon(icon, null, Modifier.size(14.dp))
                Spacer(Modifier.width(4.dp))
            }
            Text(text, style = MaterialTheme.typography.labelMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun EntryChips(entry: Entry) {
    if (entry.projects.isEmpty() && entry.cases.isEmpty() && entry.tags.isEmpty() && entry.attachmentCount == 0 && entry.drawingCount == 0) return
    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        entry.cases.forEach { Pill(it.title, Icons.Outlined.Work) }
        entry.projects.forEach { Pill(it.name, Icons.Outlined.Folder) }
        entry.tags.forEach { Pill(it, Icons.AutoMirrored.Outlined.Label) }
        if (entry.attachmentCount > 0) Pill(entry.attachmentCount.toString(), Icons.Outlined.AttachFile)
        if (entry.drawingCount > 0) Pill(entry.drawingCount.toString(), Icons.Outlined.Draw)
    }
}

/** Karte eines Eintrags wie im Tagescockpit: Typ, Zeit, Titel, Beteiligte, Auszug, Zuordnungen. */
@Composable
fun EntryCard(entry: Entry, selected: Boolean = false, showDate: Boolean = false, onClick: () -> Unit) {
    OutlinedCard(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        colors = if (selected) androidx.compose.material3.CardDefaults.outlinedCardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
        else androidx.compose.material3.CardDefaults.outlinedCardColors(),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(typeIcon(entry.type), null, Modifier.size(16.dp), tint = typeColor(entry.type))
                Spacer(Modifier.width(6.dp))
                Text(entry.typeLabel, style = MaterialTheme.typography.labelMedium, color = typeColor(entry.type))
                Spacer(Modifier.weight(1f))
                val stamp = listOfNotNull(if (showDate) shortDate(entry.date) else null, entry.time.ifEmpty { null }).joinToString(" · ")
                Text(stamp, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(entry.title, style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
            val people = when (entry.type) {
                "mail_in" -> entry.sender
                "mail_out" -> entry.recipients
                else -> entry.participants
            }
            if (people.isNotBlank()) {
                Text(people, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            if (entry.excerpt.isNotBlank()) {
                Text(entry.excerpt, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 3, overflow = TextOverflow.Ellipsis)
            }
            EntryChips(entry)
        }
    }
}

@Composable
fun TaskRow(task: Task, today: String, onToggle: () -> Unit, onOpenEntry: ((Int) -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalAlignment = Alignment.Top) {
        IconButton(onClick = onToggle) {
            Icon(
                if (task.done) Icons.Outlined.CheckCircle else Icons.Outlined.RadioButtonUnchecked,
                contentDescription = if (task.done) "Wieder öffnen: ${task.text}" else "Erledigen: ${task.text}",
                tint = if (task.done) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline,
            )
        }
        Column(Modifier.weight(1f).padding(top = 12.dp, end = 8.dp)) {
            Text(
                task.text,
                style = MaterialTheme.typography.bodyLarge,
                textDecoration = if (task.done) TextDecoration.LineThrough else null,
                color = if (task.done) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
            )
            val meta = buildList {
                when {
                    task.done -> add("Erledigt " + shortDate(task.completedAt))
                    task.due == null -> add("Ohne Datum")
                    task.due < today -> add("Überfällig · " + shortDate(task.due))
                    else -> add(relativeDate(task.due))
                }
                task.project?.let { add(it.name) }
                task.case?.let { add(it.title) }
                if (task.subtasks.isNotEmpty()) add("${task.subtasks.count { it.done != 0 }}/${task.subtasks.size} Unteraufgaben")
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    meta.joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = if (!task.done && task.due != null && task.due < today) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f, fill = false),
                )
                if (task.entryId != null && onOpenEntry != null) {
                    Text(
                        "  Zum Eintrag",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.clickable { onOpenEntry(task.entryId) },
                    )
                }
            }
        }
    }
}

@Composable
fun SectionTitle(text: String, count: Int? = null, modifier: Modifier = Modifier, action: @Composable (() -> Unit)? = null) {
    Row(modifier.fillMaxWidth().padding(top = 8.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(text, style = MaterialTheme.typography.titleMedium)
        if (count != null) {
            Spacer(Modifier.width(8.dp))
            Surface(shape = RoundedCornerShape(5.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                Text(count.toString(), Modifier.padding(horizontal = 6.dp, vertical = 1.dp), style = MaterialTheme.typography.labelSmall)
            }
        }
        Spacer(Modifier.weight(1f))
        action?.invoke()
    }
}

@Composable
fun EmptyHint(text: String, detail: String? = null, icon: ImageVector = Icons.Outlined.Description) {
    Column(Modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(icon, null, tint = MaterialTheme.colorScheme.outline)
        Spacer(Modifier.size(6.dp))
        Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        if (detail != null) Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
    }
}

@Composable
fun Loading() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
}

@Composable
fun ErrorState(message: String, onRetry: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(message, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.error)
        Spacer(Modifier.size(16.dp))
        Button(onClick = onRetry) { Text("Erneut versuchen") }
    }
}
