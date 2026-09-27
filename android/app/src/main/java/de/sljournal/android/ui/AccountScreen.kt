package de.sljournal.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import de.sljournal.android.AppViewModel
import de.sljournal.android.BuildConfig

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AccountScreen(app: AppViewModel) {
    val session by app.session.collectAsState()
    val me by app.me.collectAsState()
    var confirm by remember { mutableStateOf(false) }
    Scaffold(topBar = { TopAppBar(title = { Text("Konto") }) }) { padding ->
        Box(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()), contentAlignment = Alignment.TopCenter) {
            Column(Modifier.widthIn(max = 640.dp).fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                OutlinedCard {
                    ListItem(headlineContent = { Text("Journal") }, supportingContent = { Text(session?.server ?: "") })
                    ListItem(headlineContent = { Text("Dieses Gerät") }, supportingContent = { Text(session?.device ?: "") })
                    me?.let {
                        ListItem(headlineContent = { Text("Schuljahr") }, supportingContent = { Text(it.schoolYear) })
                        ListItem(headlineContent = { Text("Unbearbeitete Mails") }, supportingContent = { Text(it.inboxCount.toString()) })
                    }
                }
                Text(
                    "Die App ist mit einem eigenen Gerätetoken angemeldet. Es liegt verschlüsselt im Android-Keystore und verfällt nach 90 Tagen ohne Nutzung. " +
                        "Im Journal unter Einstellungen · Angemeldete Geräte können Sie dieses Gerät jederzeit abmelden – etwa bei Verlust.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    "Handschrift, Projekte, Kontakte, Einstellungen und Auswertungen bleiben der Weboberfläche vorbehalten.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedButton(onClick = { confirm = true }) {
                    Icon(Icons.AutoMirrored.Outlined.Logout, null)
                    Text("  Abmelden")
                }
                Text("Version ${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
    if (confirm) {
        AlertDialog(
            onDismissRequest = { confirm = false },
            title = { Text("Abmelden?") },
            text = { Text("Das Gerätetoken wird gelöscht. Zum erneuten Anmelden brauchen Sie Passwort und Einmalcode.") },
            confirmButton = { TextButton(onClick = { confirm = false; app.logout() }) { Text("Abmelden") } },
            dismissButton = { TextButton(onClick = { confirm = false }) { Text("Abbrechen") } },
        )
    }
}
