package de.sljournal.android.ui.voice

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.unit.dp

/** Schnellerfassung unten rechts: Sprachi darüber, „Neuer Eintrag“ darunter. */
@Composable
fun CaptureButtons(onVoice: () -> Unit, onNewEntry: () -> Unit) {
    Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        FloatingActionButton(
            onClick = onVoice,
            containerColor = MaterialTheme.colorScheme.secondaryContainer,
            contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
        ) { Icon(Icons.Outlined.Mic, contentDescription = "Sprachi aufnehmen") }
        ExtendedFloatingActionButton(
            onClick = onNewEntry,
            icon = { Icon(Icons.Outlined.Add, null) },
            text = { Text("Neuer Eintrag") },
        )
    }
}
